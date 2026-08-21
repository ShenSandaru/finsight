"""pgvector Similarity Search & Retrieval Service for FinSight (Sprint 6.2)."""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session
from app.core.exceptions import ValidationError
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger("finsight.services.retrieval")
settings = get_settings()


@dataclass
class RetrievalResult:
    """Structured data contract for retrieved document chunk results."""
    chunk_id: UUID
    document_id: UUID
    content: str
    chunk_type: str
    chunk_index: int
    page_number: int | None
    similarity: float
    metadata: dict[str, Any]


class RetrievalService:
    """
    Service responsible for vector similarity search over indexed chunks using PostgreSQL pgvector.
    Calculates cosine distance in-database, enforces top-k and similarity thresholds, and preserves metadata.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        session_factory: Any | None = None,
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.session_factory = session_factory or async_session

    async def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float | None = None,
        document_id: UUID | None = None,
        document_ids: list[UUID] | None = None,
        db: AsyncSession | None = None,
    ) -> list[RetrievalResult]:
        """
        Execute pgvector cosine similarity search against indexed document chunks.
        Applies HNSW ef_search within the database transaction for optimal index traversal.
        Preserves complete chunk metadata and descending similarity ordering.
        Supports single document_id or multi-document document_ids filtering.
        """
        # Step 1: Input Validation
        if not isinstance(query, str) or not query.strip():
            raise ValidationError(
                message="Query must be a non-empty string",
                details={"query": query},
            )

        if not isinstance(top_k, int) or top_k < 1 or top_k > settings.RETRIEVAL_MAX_TOP_K:
            raise ValidationError(
                message=f"top_k must be an integer between 1 and {settings.RETRIEVAL_MAX_TOP_K}",
                details={"top_k": top_k, "max_allowed": settings.RETRIEVAL_MAX_TOP_K},
            )

        threshold = min_similarity if min_similarity is not None else settings.RETRIEVAL_MIN_SIMILARITY
        if not isinstance(threshold, (int, float)) or threshold < 0.0 or threshold > 1.0:
            raise ValidationError(
                message="min_similarity must be a float between 0.0 and 1.0",
                details={"min_similarity": threshold},
            )

        # Step 2: Query Embedding Generation (No open database transaction)
        query_vector = await self.embedding_service.embed_query(query)

        # Step 3: In-Database pgvector Search
        # similarity = 1.0 - cosine_distance
        distance_expr = Chunk.embedding.cosine_distance(query_vector)
        similarity_expr = (1.0 - distance_expr).label("similarity")

        conditions = [
            Chunk.embedding.is_not(None),
            Document.status == "indexed",
            (1.0 - distance_expr) >= threshold,
        ]

        if document_ids:
            # Multi-document filtering takes precedence
            conditions.append(Chunk.document_id.in_(document_ids))
        elif document_id is not None:
            conditions.append(Chunk.document_id == document_id)

        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.content,
                Chunk.chunk_type,
                Chunk.chunk_index,
                Chunk.page_number,
                Chunk.metadata_,
                similarity_expr,
            )
            .join(Document, Document.id == Chunk.document_id)
            .where(and_(*conditions))
            .order_by(
                similarity_expr.desc(),
                Chunk.chunk_index.asc(),
                Chunk.id.asc(),
            )
            .limit(top_k)
        )

        if db is not None:
            if settings.HNSW_ENABLED and settings.HNSW_EF_SEARCH > 0:
                try:
                    await db.execute(text(f"SET LOCAL hnsw.ef_search = {int(settings.HNSW_EF_SEARCH)}"))
                except Exception as exc:
                    logger.debug("Could not set local hnsw.ef_search: %s", exc)
            result = await db.execute(stmt)
            rows = result.all()
        else:
            async with self.session_factory() as session:
                if settings.HNSW_ENABLED and settings.HNSW_EF_SEARCH > 0:
                    try:
                        await session.execute(text(f"SET LOCAL hnsw.ef_search = {int(settings.HNSW_EF_SEARCH)}"))
                    except Exception as exc:
                        logger.debug("Could not set local hnsw.ef_search: %s", exc)
                result = await session.execute(stmt)
                rows = result.all()

        # Step 4: Map rows to RetrievalResult dataclasses
        results = [
            RetrievalResult(
                chunk_id=row.id,
                document_id=row.document_id,
                content=row.content,
                chunk_type=row.chunk_type,
                chunk_index=row.chunk_index,
                page_number=row.page_number,
                similarity=round(float(row.similarity), 6),
                metadata=row.metadata_ if isinstance(row.metadata_, dict) else {},
            )
            for row in rows
        ]

        logger.info(
            "Vector search for query '%s' returned %d chunks (top_k=%d, min_sim=%.2f, doc_filter=%s)",
            query[:50],
            len(results),
            top_k,
            threshold,
            document_id,
        )

        return results
