"""RAG API endpoints for grounded financial question answering (Sprint 7.1)."""

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.models.user import User
from app.core.database import get_db
from app.schemas.rag import RAGRequest, RAGResponseSchema, CitationResponse
from app.services.rag_service import RAGService

logger = logging.getLogger("finsight.api.routes.rag")
router = APIRouter(prefix="/rag", tags=["RAG & Question Answering"])


@router.post(
    "/query",
    response_model=RAGResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Grounded financial question answering with document citations",
    description="Retrieves relevant document chunks using pgvector and generates a grounded financial answer via Gemini.",
)
async def query_rag(
    request: RAGRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RAGResponseSchema:
    """
    Execute grounded financial question answering over indexed document chunks scoped to user.
    Returns the generated answer with structured source citations.
    """
    rag_service = RAGService()
    try:
        response = await rag_service.answer(
            query=request.query,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
            document_id=request.document_id,
            document_ids=request.document_ids,
            user_id=current_user.id,
            db=db,
        )

        citation_items = [
            CitationResponse(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                page_number=c.page_number,
                chunk_type=c.chunk_type,
                similarity=c.similarity,
                statement_type=c.statement_type,
                fiscal_periods=c.fiscal_periods,
            )
            for c in response.citations
        ]

        return RAGResponseSchema(
            query=response.query,
            answer=response.answer,
            citations=citation_items,
            retrieved_chunks=response.retrieved_chunks,
            grounded=response.grounded,
        )
    finally:
        await rag_service.generation_service.close()
        await rag_service.retrieval_service.embedding_service.close()
