"""API routes for Conversation Sessions & Multi-Turn Queries (Sprint 8.2)."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.conversation import (
    CreateSessionRequest,
    ConversationSessionResponse,
    ConversationMessageResponse,
    ConversationQueryRequest,
    ConversationQueryResponse,
)
from app.services.conversation_service import ConversationService

logger = logging.getLogger("finsight.api.routes.conversations")
router = APIRouter(prefix="/conversations", tags=["Conversational Memory & Multi-Turn RAG"])


@router.post(
    "",
    response_model=ConversationSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation session",
)
async def create_session(
    request: CreateSessionRequest = CreateSessionRequest(),
    db: AsyncSession = Depends(get_db),
) -> ConversationSessionResponse:
    """Initialize an isolated conversation session for multi-turn research."""
    conv_service = ConversationService()
    return await conv_service.create_session(title=request.title, db=db)


@router.get(
    "/{session_id}",
    response_model=ConversationSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get conversation session metadata",
)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ConversationSessionResponse:
    """Retrieve metadata and message count for a specific conversation session."""
    conv_service = ConversationService()
    return await conv_service.get_session(session_id=session_id, db=db)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a conversation session and its history",
)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a conversation session and cascade delete all associated messages."""
    conv_service = ConversationService()
    await conv_service.delete_session(session_id=session_id, db=db)
    return {"message": "Session deleted successfully", "session_id": str(session_id)}


@router.get(
    "/{session_id}/messages",
    response_model=list[ConversationMessageResponse],
    status_code=status.HTTP_200_OK,
    summary="Get chronological messages for a conversation session",
)
async def get_session_messages(
    session_id: UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[ConversationMessageResponse]:
    """Retrieve messages for a session in chronological order."""
    conv_service = ConversationService()
    # Confirm session exists
    await conv_service.get_session(session_id=session_id, db=db)
    messages = await conv_service.get_recent_messages(session_id=session_id, limit=limit, db=db)
    return [
        ConversationMessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post(
    "/{session_id}/query",
    response_model=ConversationQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a multi-turn grounded financial question in a session",
)
async def query_conversation(
    session_id: UUID,
    request: ConversationQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> ConversationQueryResponse:
    """
    Execute a conversation-aware query within a session:
    1. Persists user query.
    2. Resolves follow-ups against prior messages.
    3. Retrieves grounded evidence and generates an answer via RAGService.
    4. Persists assistant answer.
    5. Returns grounded answer with structured citations.
    """
    conv_service = ConversationService()
    try:
        return await conv_service.process_query(
            session_id=session_id,
            query=request.query,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
            document_id=request.document_id,
            document_ids=request.document_ids,
            db=db,
        )
    finally:
        await conv_service.rag_service.generation_service.close()
        await conv_service.rag_service.retrieval_service.embedding_service.close()
