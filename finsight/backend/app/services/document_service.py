import uuid
import aiofiles
from pathlib import Path

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import FileValidationError, DocumentNotFoundError
from app.core.storage import StorageBackend, get_storage_backend
from app.models.document import Document
from app.models.chunk import Chunk

settings = get_settings()


class DocumentService:
    """Service for handling document operations."""

    def __init__(self, db: AsyncSession, storage: StorageBackend | None = None):
        self.db = db
        self.storage = storage or get_storage_backend()

    def validate_file_content(self, file_extension: str, content: bytes) -> None:
        """
        Validate actual file content using magic bytes and text integrity checks.
        Raises FileValidationError if content does not match the claimed file type.
        """
        # Reject 0-byte files
        if len(content) == 0:
            raise FileValidationError(
                message="Uploaded file is empty (0 bytes)",
                details={"file_size": 0}
            )

        if file_extension == "pdf":
            # PDF standard specification: must begin with %PDF- header
            if not content.startswith(b"%PDF-"):
                raise FileValidationError(
                    message="Invalid PDF file format: missing '%PDF-' header signature",
                    details={"file_extension": "pdf"}
                )

        elif file_extension in ("txt", "csv"):
            # Ensure text-like decodability without binary null bytes
            if b"\x00" in content:
                raise FileValidationError(
                    message=f"Invalid {file_extension.upper()} file: contains binary null bytes",
                    details={"file_extension": file_extension}
                )

            # Attempt safe decoding (UTF-8, UTF-8-sig, or Latin-1)
            decoded = False
            for encoding in ("utf-8", "utf-8-sig", "latin-1"):
                try:
                    content.decode(encoding)
                    decoded = True
                    break
                except UnicodeDecodeError:
                    continue

            if not decoded:
                raise FileValidationError(
                    message=f"Invalid {file_extension.upper()} file: unable to decode text content",
                    details={"file_extension": file_extension}
                )

    async def validate_file(self, file: UploadFile) -> tuple[str, int, bytes]:
        """
        Validate uploaded file type, size, and content.
        Returns (file_extension, file_size, content) if valid.
        Raises FileValidationError if invalid.
        """
        # Check filename exists
        if not file.filename:
            raise FileValidationError(
                message="Filename is required",
                details={"field": "filename"}
            )

        # Extract sanitized file extension
        safe_name = Path(file.filename).name
        if "." not in safe_name:
            raise FileValidationError(
                message="File extension is required",
                details={"filename": safe_name}
            )

        file_extension = safe_name.split(".")[-1].lower()

        # Check allowed types
        if file_extension not in settings.ALLOWED_FILE_TYPES:
            raise FileValidationError(
                message=f"File type '{file_extension}' not allowed. Allowed types: {settings.ALLOWED_FILE_TYPES}",
                details={"file_extension": file_extension, "allowed_types": settings.ALLOWED_FILE_TYPES}
            )

        # Stream-read file content in 64KB chunks to abort early on oversized uploads before buffering
        chunks = []
        file_size = 0
        chunk_size = 64 * 1024  # 64 KB

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > settings.MAX_FILE_SIZE:
                max_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
                raise FileValidationError(
                    message=f"File size exceeds maximum allowed size of {max_mb}MB",
                    details={"file_size": file_size, "max_file_size": settings.MAX_FILE_SIZE}
                )
            chunks.append(chunk)

        content = b"".join(chunks)

        # Validate content / magic bytes
        self.validate_file_content(file_extension, content)

        # Reset file position for downstream reading if needed
        await file.seek(0)

        return file_extension, file_size, content

    async def save_file(self, content: bytes, original_filename: str, document_id: uuid.UUID) -> str:
        """
        Save validated file bytes to storage using the configured StorageBackend.
        Returns the resolved storage key.
        """
        storage_key = self.storage.get_document_key(document_id, original_filename)
        await self.storage.save(storage_key, content)
        return storage_key

    async def create_document(
        self,
        filename: str,
        file_type: str,
        file_size: int,
        user_id: uuid.UUID,
        title: str | None = None,
        description: str | None = None,
        source: str | None = None,
    ) -> Document:
        """
        Create a new document record in the database belonging to user_id.
        """
        document = Document(
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            title=title,
            description=description,
            source=source,
            status="pending",
        )

        self.db.add(document)
        await self.db.flush()

        return document

    async def upload_document(
        self,
        file: UploadFile,
        user_id: uuid.UUID,
        title: str | None = None,
        description: str | None = None,
        source: str | None = None,
    ) -> Document:
        """
        Handle complete document upload process scoped to user_id.
        """
        # Step 1: Validate type, size, and content magic bytes
        file_extension, file_size, content = await self.validate_file(file)

        # Step 2: Create DB record
        safe_filename_base = Path(file.filename).name if file.filename else "unknown"
        document = await self.create_document(
            filename=safe_filename_base,
            file_type=file_extension,
            file_size=file_size,
            user_id=user_id,
            title=title,
            description=description,
            source=source,
        )

        # Step 3: Save file to disk
        await self.save_file(content, safe_filename_base, document.id)

        return document

    async def get_document(self, document_id: uuid.UUID, user_id: uuid.UUID | None = None) -> Document | None:
        """Get a single document by ID, optionally verifying ownership."""
        query = select(Document).where(Document.id == document_id)
        if user_id is not None:
            query = query.where(Document.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all_documents(self, user_id: uuid.UUID | None = None) -> list[Document]:
        """Get all documents belonging to user_id."""
        query = select(Document).order_by(Document.created_at.desc())
        if user_id is not None:
            query = query.where(Document.user_id == user_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_document(self, document_id: uuid.UUID, user_id: uuid.UUID | None = None) -> bool:
        """
        Delete a document and its file if owned by user_id.
        Returns True if deleted, False if not found.
        """
        document = await self.get_document(document_id, user_id=user_id)

        if not document:
            return False

        # Delete the file from storage via StorageBackend
        storage_key = self.storage.get_document_key(document_id, document.filename)
        await self.storage.delete(storage_key)

        # Delete from database
        await self.db.delete(document)

        return True

    async def get_chunk(self, chunk_id: uuid.UUID, user_id: uuid.UUID | None = None) -> Chunk | None:
        """
        Get a specific evidence chunk by ID with its parent document relationship loaded,
        optionally verifying user ownership.
        """
        query = (
            select(Chunk)
            .options(selectinload(Chunk.document))
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.id == chunk_id)
        )
        if user_id is not None:
            query = query.where(Document.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()