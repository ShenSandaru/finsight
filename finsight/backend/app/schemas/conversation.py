"""Pydantic schemas for Conversation Sessions & Multi-Turn Queries (Sprint 8.2)."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.schemas.rag import CitationResponse, RAGResponseSchema


class CreateSessionRequest(BaseModel):
    """Payload to initialize a new conversation session."""
    title: str | None = Field(None, max_length=255, description="Optional title for the research conversation session")


class ConversationMessageResponse(BaseModel):
    """Payload representing a persisted user or assistant message."""
    id: UUID = Field(..., description="Unique message UUID")
    session_id: UUID = Field(..., description="Parent session UUID")
    role: str = Field(..., description="Message author role: 'user' or 'assistant'")
    content: str = Field(..., description="Raw message text content")
    created_at: datetime = Field(..., description="Timestamp when message was stored")


class ConversationSessionResponse(BaseModel):
    """Payload representing session metadata and status."""
    id: UUID = Field(..., description="Unique conversation session UUID")
    title: str | None = Field(None, description="Conversation session title")
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Session last updated timestamp")
    message_count: int = Field(0, description="Total number of messages in session")


class ConversationQueryRequest(BaseModel):
    """Payload for asking a multi-turn financial question within an existing session."""
    query: str = Field(..., min_length=1, max_length=8000, description="User financial question or follow-up query")
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of document chunks to retrieve")
    min_similarity: float = Field(0.30, ge=0.0, le=1.0, description="Minimum relevance threshold score")
    document_id: UUID | None = Field(None, description="Optional document UUID filter to scope retrieval")
    document_ids: list[UUID] | None = Field(None, description="Optional list of document UUIDs for multi-document filtering")


class ConversationQueryResponse(BaseModel):
    """Response payload for multi-turn grounded question answering."""
    session_id: UUID = Field(..., description="Session UUID for this conversation")
    query: str = Field(..., description="Original user question")
    resolved_query: str | None = Field(None, description="Conversation-aware retrieval query if rewritten for context")
    answer: str = Field(..., description="Grounded financial answer referencing [SOURCE N] citations")
    citations: list[CitationResponse] = Field(default_factory=list, description="Ordered source citations backing answer")
    retrieved_chunks: int = Field(..., description="Total retrieved chunks included in evidence context")
    grounded: bool = Field(..., description="True if answer is backed by retrieved evidence; False if insufficient")
