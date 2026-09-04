import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    """Schema for document data returned by the API."""

    id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    title: str | None = None
    description: str | None = None
    source: str | None = None
    status: str
    processing_error: str | None = None
    total_pages: int | None = None
    total_chunks: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """Schema for the response after uploading a document."""

    message: str
    document: DocumentResponse


class DocumentListResponse(BaseModel):
    """Schema for listing multiple documents."""

    total: int
    documents: list[DocumentResponse]


class DocumentChunkResponse(BaseModel):
    """Schema for individual document evidence chunk returned by the API."""

    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str | None = None
    document_filename: str | None = None
    content: str
    chunk_type: str
    chunk_index: int
    page_number: int | None = None
    metadata: dict | None = None
    created_at: datetime

    class Config:
        from_attributes = True