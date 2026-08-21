"""Gemini Embedding Service using the official google-genai Python SDK (Sprint 6.1)."""

import asyncio
import hashlib
import logging
import math
from typing import Any
from uuid import UUID

from google import genai
from google.genai import types, errors

from app.core.config import get_settings
from app.core.exceptions import ProcessingError
from app.models.chunk import Chunk

logger = logging.getLogger("finsight.services.embedding")
settings = get_settings()


class FakeGenAIClient:
    """
    Deterministic, offline fake Gemini client for unit and integration tests.
    Generates deterministic 1536-dimensional float vectors based on input text hashes.
    """

    def __init__(self, force_error: Exception | None = None, dimension: int = 1536):
        self.force_error = force_error
        self.dimension = dimension
        self.call_count = 0
        self.aio = self

    class Models:
        def __init__(self, parent: "FakeGenAIClient"):
            self.parent = parent

        async def embed_content(
            self,
            model: str,
            contents: list[str],
            config: Any = None,
        ) -> Any:
            self.parent.call_count += 1
            if self.parent.force_error:
                raise self.parent.force_error

            dim = self.parent.dimension
            embeddings = []
            for text in contents:
                # Generate deterministic vector using sha256
                seed_bytes = hashlib.sha256(text.encode("utf-8")).digest()
                seed_int = int.from_bytes(seed_bytes[:4], "big")
                # Create vector with unit norm
                raw_vector = [math.sin(seed_int + i) for i in range(dim)]
                norm = math.sqrt(sum(x * x for x in raw_vector)) or 1.0
                norm_vector = [x / norm for x in raw_vector]
                embeddings.append(types.ContentEmbedding(values=norm_vector))

            class FakeResponse:
                def __init__(self, embs: list[Any]):
                    self.embeddings = embs

            return FakeResponse(embeddings)

    @property
    def models(self) -> Models:
        return self.Models(self)

    async def aclose(self) -> None:
        """Simulate async cleanup."""
        pass


class EmbeddingService:
    """
    Service responsible for generating 1536-dimensional vector embeddings using Google GenAI SDK.
    Supports batching, bounded exponential backoff retries, and strict dimension validation.
    """

    def __init__(
        self,
        client: Any | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        batch_size: int | None = None,
        max_retries: int | None = None,
        timeout: float | None = None,
    ):
        self.model = model or settings.EMBEDDING_MODEL
        self.dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self.max_retries = max_retries if max_retries is not None else settings.EMBEDDING_MAX_RETRIES
        self.timeout = timeout or settings.EMBEDDING_TIMEOUT_SECONDS

        if client is not None:
            self.client = client
            self._owns_client = False
        elif settings.EMBEDDING_PROVIDER == "fake":
            self.client = FakeGenAIClient(dimension=self.dimensions)
            self._owns_client = True
        else:
            if not settings.GEMINI_API_KEY:
                raise ProcessingError(
                    message="GEMINI_API_KEY configuration is missing",
                    details={"provider": "gemini"},
                )
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self._owns_client = True

    async def close(self) -> None:
        """Close async client connections if owned by this service."""
        if self._owns_client and hasattr(self.client, "aio") and hasattr(self.client.aio, "aclose"):
            try:
                await self.client.aio.aclose()
            except Exception as exc:
                logger.warning("Error closing Gemini async client: %s", exc)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate 1536-dimensional embeddings for a list of texts in sequential batches.
        Strictly preserves 1-to-1 input index ordering and validates vector dimensions.
        """
        if not texts:
            raise ProcessingError(
                message="Cannot generate embeddings for an empty text list",
                details={"input_count": 0},
            )

        for idx, text in enumerate(texts):
            if not isinstance(text, str):
                raise ProcessingError(
                    message=f"Invalid input at index {idx}: expected str, got {type(text).__name__}",
                    details={"index": idx},
                )
            if not text.strip():
                raise ProcessingError(
                    message=f"Invalid input at index {idx}: empty or whitespace-only text chunk",
                    details={"index": idx},
                )

        all_vectors: list[list[float]] = []
        config = types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=self.dimensions,
        )

        total_batches = (len(texts) + self.batch_size - 1) // self.batch_size
        for b_idx in range(total_batches):
            start = b_idx * self.batch_size
            end = min(start + self.batch_size, len(texts))
            batch = texts[start:end]

            batch_vectors = await self._embed_batch_with_retry(batch, config)
            all_vectors.extend(batch_vectors)

        # Final verification of output count and dimensions
        if len(all_vectors) != len(texts):
            raise ProcessingError(
                message=f"Embedding output count mismatch: expected {len(texts)}, got {len(all_vectors)}",
                details={"expected": len(texts), "actual": len(all_vectors)},
            )

        for v_idx, vec in enumerate(all_vectors):
            if len(vec) != self.dimensions:
                raise ProcessingError(
                    message=f"Embedding dimension mismatch at index {v_idx}: expected {self.dimensions}, got {len(vec)}",
                    details={"index": v_idx, "expected": self.dimensions, "actual": len(vec)},
                )

        return all_vectors

    async def _embed_batch_with_retry(
        self,
        batch: list[str],
        config: types.EmbedContentConfig,
    ) -> list[list[float]]:
        """Call Gemini embed_content for a batch with bounded exponential backoff on transient errors."""
        attempt = 0
        backoff_base = 0.5

        while True:
            try:
                # Call modern asynchronous Google GenAI SDK
                response = await asyncio.wait_for(
                    self.client.aio.models.embed_content(
                        model=self.model,
                        contents=batch,
                        config=config,
                    ),
                    timeout=self.timeout,
                )

                if not response or not hasattr(response, "embeddings") or not response.embeddings:
                    raise ProcessingError(
                        message="Malformed or empty response from Gemini Embedding API",
                        details={"model": self.model},
                    )

                batch_vectors: list[list[float]] = []
                for emb in response.embeddings:
                    vec = list(emb.values) if hasattr(emb, "values") and emb.values else []
                    if len(vec) != self.dimensions:
                        raise ProcessingError(
                            message=f"Gemini returned invalid embedding dimension: expected {self.dimensions}, got {len(vec)}",
                            details={"expected": self.dimensions, "actual": len(vec)},
                        )
                    batch_vectors.append(vec)

                return batch_vectors

            except (ProcessingError, ValueError, TypeError) as non_retryable:
                # Non-transient errors must fail immediately
                raise non_retryable

            except Exception as exc:
                # Check for transient exceptions
                is_transient = self._is_transient_error(exc)
                if not is_transient or attempt >= self.max_retries:
                    logger.error(
                        "Gemini embedding batch failed (attempt %d/%d, transient=%s): %s",
                        attempt + 1,
                        self.max_retries + 1,
                        is_transient,
                        type(exc).__name__,
                    )
                    raise ProcessingError(
                        message=f"Gemini embedding API call failed: {type(exc).__name__}",
                        details={"model": self.model, "attempt": attempt + 1},
                    ) from exc

                attempt += 1
                delay = backoff_base * (2 ** (attempt - 1))
                logger.warning(
                    "Transient error in Gemini embedding call (%s). Retrying in %.2fs (attempt %d/%d)...",
                    type(exc).__name__,
                    delay,
                    attempt,
                    self.max_retries,
                )
                await asyncio.sleep(delay)

    @staticmethod
    def _is_transient_error(exc: Exception) -> bool:
        """Determine if an exception is transient (rate limit, temporary server error, network timeout)."""
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            return True

        if isinstance(exc, errors.APIError):
            # 429 = Rate Limit, 500 = Internal, 503 = Service Unavailable, 504 = Gateway Timeout
            code = getattr(exc, "code", None)
            if code in (429, 500, 502, 503, 504):
                return True

        # Check for standard network/connection errors
        exc_str = str(exc).lower()
        if any(w in exc_str for w in ("rate limit", "quota", "connection", "timeout", "unavailable", "503", "429")):
            return True

        return False

    async def embed_chunks(self, chunks: list[Chunk]) -> list[tuple[UUID, list[float]]]:
        """
        Embed a list of database Chunk ORM objects.
        Returns a list of paired tuples: (chunk_id, 1536_dim_vector).
        """
        if not chunks:
            return []

        texts = [c.content for c in chunks]
        vectors = await self.embed_texts(texts)

        return [(c.id, vec) for c, vec in zip(chunks, vectors)]
