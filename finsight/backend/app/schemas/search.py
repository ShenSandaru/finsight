"""Pydantic schemas for Vector Retrieval & Search API (Sprint 6.2)."""

from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request payload for semantic vector search."""
    query: str = Field(..., min_length=1, description="Natural language search query")
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of chunks to return")
    min_similarity: float = Field(0.0, ge=0.0, le=1.0, description="Minimum cosine similarity score (0.0 to 1.0)")
    document_id: UUID | None = Field(None, description="Optional document UUID filter to restrict search scope")
    document_ids: list[UUID] | None = Field(None, description="Optional list of document UUIDs for multi-document filtering")


class SearchResultItem(BaseModel):
    """Individual retrieved document chunk result."""
    chunk_id: UUID = Field(..., description="Unique identifier of the chunk")
    document_id: UUID = Field(..., description="Document UUID owning this chunk")
    content: str = Field(..., description="Chunk text or Markdown table content")
    chunk_type: str = Field(..., description="Type of chunk: 'text' or 'table'")
    chunk_index: int = Field(..., description="0-indexed position within the document")
    page_number: int | None = Field(None, description="1-indexed source page number")
    similarity: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary (e.g. table semantics)")


class SearchResponse(BaseModel):
    """Response payload returning retrieved chunks."""
    query: str = Field(..., description="Echo of original search query")
    total_results: int = Field(..., description="Count of retrieved chunks matching criteria")
    results: list[SearchResultItem] = Field(..., description="Ordered list of retrieved chunks (highest similarity first)")
