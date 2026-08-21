"""Generation Service using Google GenAI SDK for Grounded Financial Answers (Sprint 7.1)."""

import asyncio
import logging
from typing import Any

from google import genai
from google.genai import types, errors

from app.core.config import get_settings
from app.core.exceptions import ProcessingError, ValidationError
from app.services.embedding_service import FakeGenAIClient

logger = logging.getLogger("finsight.services.generation")
settings = get_settings()

GROUNDING_SYSTEM_INSTRUCTION = (
    "You are a financial document question-answering assistant.\n"
    "Use ONLY the supplied FinSight document context.\n\n"
    "Rules:\n"
    "1. Never use outside knowledge.\n"
    "2. Never invent financial values, dates, periods, currencies, or units.\n"
    "3. Preserve exact financial units and currency (e.g., millions, billions, $, EUR).\n"
    "4. Distinguish annual, quarterly, YTD, and point-in-time values.\n"
    "5. When comparing periods, identify the periods explicitly.\n"
    "6. Use only evidence present in the supplied context.\n"
    "7. Cite supporting evidence using [SOURCE N] (e.g., [SOURCE 1]).\n"
    "8. Never fabricate a [SOURCE N] identifier that is not in the provided evidence.\n"
    "9. If evidence is insufficient, clearly state that the indexed documents do not provide enough information.\n"
    "10. Do not claim information unsupported by the supplied evidence.\n"
    "11. Keep answers concise, factual, and professional."
)


class GenerationService:
    """
    Service responsible for calling Gemini asynchronously to generate grounded financial answers.
    Supports system instructions, low temperature, token bounds, and retry with exponential backoff.
    """

    def __init__(
        self,
        client: Any | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        max_retries: int | None = None,
        timeout: float | None = None,
    ):
        self.model = model or settings.GEMINI_MODEL
        self.temperature = temperature if temperature is not None else settings.GEMINI_TEMPERATURE
        self.max_output_tokens = max_output_tokens or settings.GEMINI_MAX_OUTPUT_TOKENS
        self.max_retries = max_retries if max_retries is not None else settings.GEMINI_MAX_RETRIES
        self.timeout = timeout or settings.GEMINI_GENERATION_TIMEOUT_SECONDS

        if client is not None:
            self.client = client
            self._owns_client = False
        elif settings.GEMINI_GENERATION_PROVIDER == "fake" or settings.EMBEDDING_PROVIDER == "fake":
            self.client = FakeGenAIClient()
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
                logger.warning("Error closing Gemini generation async client: %s", exc)

    async def generate_answer(
        self,
        query: str,
        context: str,
    ) -> str:
        """
        Generate a grounded financial answer for a query given retrieved evidence context.
        Calls Gemini asynchronously with retry policy and system instructions.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValidationError(
                message="Query must be a non-empty string",
                details={"query": query},
            )

        if not isinstance(context, str) or not context.strip():
            raise ValidationError(
                message="Context must be a non-empty string",
                details={"context_length": len(context) if isinstance(context, str) else 0},
            )

        prompt = (
            f"Financial question:\n{query.strip()}\n\n"
            f"Retrieved FinSight evidence:\n{context.strip()}\n\n"
            f"Answer the question using only this evidence."
        )

        config = types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            system_instruction=GROUNDING_SYSTEM_INSTRUCTION,
        )

        attempt = 0
        backoff_base = 0.5

        while True:
            try:
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=config,
                    ),
                    timeout=self.timeout,
                )

                if not response:
                    raise ProcessingError(
                        message="Empty response received from Gemini Generation API",
                        details={"model": self.model},
                    )

                text = getattr(response, "text", "")
                if not text or not str(text).strip():
                    raise ProcessingError(
                        message="Gemini returned an empty or blank text answer",
                        details={"model": self.model},
                    )

                return str(text).strip()

            except (ValidationError, ProcessingError) as non_retryable:
                raise non_retryable

            except Exception as exc:
                is_transient = self._is_transient_error(exc)
                if not is_transient or attempt >= self.max_retries:
                    logger.error(
                        "Gemini answer generation failed (attempt %d/%d, transient=%s): %s",
                        attempt + 1,
                        self.max_retries + 1,
                        is_transient,
                        type(exc).__name__,
                    )
                    raise ProcessingError(
                        message=f"Gemini generation API call failed: {type(exc).__name__}",
                        details={"model": self.model, "attempt": attempt + 1},
                    ) from exc

                attempt += 1
                delay = backoff_base * (2 ** (attempt - 1))
                logger.warning(
                    "Transient error in Gemini generation call (%s). Retrying in %.2fs (attempt %d/%d)...",
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
            code = getattr(exc, "code", None)
            if code in (429, 500, 502, 503, 504):
                return True

        exc_str = str(exc).lower()
        if any(w in exc_str for w in ("rate limit", "quota", "connection", "timeout", "unavailable", "503", "429")):
            return True

        return False
