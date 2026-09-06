"""Search and Vector Retrieval API endpoints (Sprint 6.2)."""

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.models.user import User
from app.core.database import get_db
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger("finsight.api.routes.search")
router = APIRouter(prefix="/search", tags=["Search & Retrieval"])


@router.post(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Vector similarity search across indexed document chunks",
    description="Embeds the search query using Gemini (RETRIEVAL_QUERY task type) and executes pgvector cosine similarity search in PostgreSQL.",
)
async def search_chunks(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """
    Search indexed chunks using semantic vector similarity.
    Returns ranked chunk items without generating LLM answers.
    """
    retrieval_service = RetrievalService()
    try:
        results = await retrieval_service.search(
            query=request.query,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
            document_id=request.document_id,
            document_ids=request.document_ids,
            user_id=current_user.id,
            db=db,
        )

        items = [
            SearchResultItem(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                content=r.content,
                chunk_type=r.chunk_type,
                chunk_index=r.chunk_index,
                page_number=r.page_number,
                similarity=r.similarity,
                metadata=r.metadata,
            )
            for r in results
        ]

        return SearchResponse(
            query=request.query,
            total_results=len(items),
            results=items,
        )
    finally:
        await retrieval_service.embedding_service.close()
