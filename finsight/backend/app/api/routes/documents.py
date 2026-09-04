import uuid
import logging

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tasks import enqueue_task
from app.core.exceptions import DocumentNotFoundError, ChunkNotFoundError, ExternalServiceError
from app.services.document_service import DocumentService
from app.schemas.document import (
    DocumentResponse,
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentChunkResponse,
)

logger = logging.getLogger("finsight.api.documents")
router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    description: str | None = Form(None),
    source: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a new document (PDF, TXT, or CSV).

    The document will be saved, committed, and queued for background processing.
    """
    service = DocumentService(db)
    document = await service.upload_document(
        file=file,
        title=title,
        description=description,
        source=source,
    )

    # Explicitly commit DB transaction before enqueueing task to prevent worker race conditions
    await db.commit()

    # Enqueue background ingestion job
    try:
        await enqueue_task("process_document", str(document.id))
    except Exception as exc:
        logger.error("Failed to enqueue ingestion task for document '%s': %s", document.id, exc)
        raise ExternalServiceError(
            message="Document saved, but failed to enqueue background processing task",
            details={"document_id": str(document.id), "error": str(exc)},
        ) from exc

    return DocumentUploadResponse(
        message="Document uploaded successfully",
        document=DocumentResponse.model_validate(document),
    )


@router.get(
    "/",
    response_model=DocumentListResponse,
)
async def list_documents(
    db: AsyncSession = Depends(get_db),
):
    """
    Get all uploaded documents.
    """
    service = DocumentService(db)
    documents = await service.get_all_documents()

    return DocumentListResponse(
        total=len(documents),
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
    )


@router.get(
    "/chunks/{chunk_id}",
    response_model=DocumentChunkResponse,
)
async def get_chunk(
    chunk_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific evidence chunk by ID for citation inspection.
    """
    service = DocumentService(db)
    chunk = await service.get_chunk(chunk_id)

    if not chunk:
        raise ChunkNotFoundError(
            message=f"Evidence chunk with ID '{chunk_id}' not found",
            details={"chunk_id": str(chunk_id)}
        )

    return DocumentChunkResponse(
        id=chunk.id,
        document_id=chunk.document_id,
        document_title=chunk.document.title if chunk.document else None,
        document_filename=chunk.document.filename if chunk.document else None,
        content=chunk.content,
        chunk_type=chunk.chunk_type,
        chunk_index=chunk.chunk_index,
        page_number=chunk.page_number,
        metadata=chunk.metadata_,
        created_at=chunk.created_at,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific document by ID.
    """
    service = DocumentService(db)
    document = await service.get_document(document_id)

    if not document:
        raise DocumentNotFoundError(
            message=f"Document with ID '{document_id}' not found",
            details={"document_id": str(document_id)}
        )

    return DocumentResponse.model_validate(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a document and its associated file.
    """
    service = DocumentService(db)
    deleted = await service.delete_document(document_id)

    if not deleted:
        raise DocumentNotFoundError(
            message=f"Document with ID '{document_id}' not found",
            details={"document_id": str(document_id)}
        )

    return None