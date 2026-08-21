"""Pydantic schemas for RAG Query & Grounded Answer Generation (Sprint 7.1)."""

from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class RAGRequest(BaseModel):
    """Request payload for grounded financial question answering."""
    query: str = Field(..., min_length=1, description="Financial question to answer using indexed evidence")
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of chunks to retrieve for context assembly")
    min_similarity: float = Field(0.30, ge=0.0, le=1.0, description="Minimum similarity relevance score threshold")
    document_id: UUID | None = Field(None, description="Optional document UUID filter to restrict research scope")
    document_ids: list[UUID] | None = Field(None, description="Optional list of document UUIDs for multi-document filtering")


class CitationResponse(BaseModel):
    """Structured citation metadata for a document chunk used in the answer."""
    chunk_id: UUID = Field(..., description="Unique chunk UUID")
    document_id: UUID = Field(..., description="Document UUID owning this chunk")
    page_number: int | None = Field(None, description="1-indexed source page number")
    chunk_type: str = Field(..., description="Chunk type: 'text' or 'table'")
    similarity: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    statement_type: str | None = Field(None, description="Financial statement type (e.g. 'income_statement')")
    fiscal_periods: list[str] = Field(default_factory=list, description="Extracted fiscal periods (e.g. ['2025', '2024'])")


class RAGResponseSchema(BaseModel):
    """Response payload returning grounded financial answer and structured citations."""
    query: str = Field(..., description="Echo of original user query")
    answer: str = Field(..., description="Grounded financial answer referencing [SOURCE N] citations")
    citations: list[CitationResponse] = Field(..., description="Ordered list of source citations backing the answer")
    retrieved_chunks: int = Field(..., description="Total count of retrieved chunks included in evidence context")
    grounded: bool = Field(..., description="True if answer is backed by retrieved evidence; False if evidence was insufficient")
