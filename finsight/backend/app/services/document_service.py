import uuid
import aiofiles
from pathlib import Path

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import FileValidationError, DocumentNotFoundError
from app.models.document import Document
from app.models.chunk import Chunk

settings = get_settings()


class DocumentService:
    """Service for handling document operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

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

        # Read file content to check size and validate magic bytes
        content = await file.read()
        file_size = len(content)

        # Check file size
        if file_size > settings.MAX_FILE_SIZE:
            max_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
            raise FileValidationError(
                message=f"File size exceeds maximum allowed size of {max_mb}MB",
                details={"file_size": file_size, "max_file_size": settings.MAX_FILE_SIZE}
            )

        # Validate content / magic bytes
        self.validate_file_content(file_extension, content)

        # Reset file position for downstream reading if needed
        await file.seek(0)

        return file_extension, file_size, content

    async def save_file(self, content: bytes, original_filename: str, document_id: uuid.UUID) -> Path:
        """
        Save validated file bytes to storage using safe path handling.
        Returns the path where the file was saved.
        """
        # Create storage directory if it doesn't exist
        settings.DOCUMENTS_PATH.mkdir(parents=True, exist_ok=True)

        # Extract only the base name to prevent path traversal attacks (../, absolute paths)
        safe_filename_base = Path(original_filename).name
        safe_filename = f"{document_id}_{safe_filename_base}"
        file_path = settings.DOCUMENTS_PATH / safe_filename

        # Save file using async I/O
        async with aiofiles.open(file_path, "wb") as out_file:
            await out_file.write(content)

        return file_path

    async def create_document(
        self,
        filename: str,
        file_type: str,
        file_size: int,
        title: str | None = None,
        description: str | None = None,
        source: str | None = None,
    ) -> Document:
        """
        Create a new document record in the database.
        """
        document = Document(
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
        title: str | None = None,
        description: str | None = None,
        source: str | None = None,
    ) -> Document:
        """
        Handle complete document upload process.
        """
        # Step 1: Validate type, size, and content magic bytes
        file_extension, file_size, content = await self.validate_file(file)

        # Step 2: Create DB record
        safe_filename_base = Path(file.filename).name if file.filename else "unknown"
        document = await self.create_document(
            filename=safe_filename_base,
            file_type=file_extension,
            file_size=file_size,
            title=title,
            description=description,
            source=source,
        )

        # Step 3: Save file to disk
        await self.save_file(content, safe_filename_base, document.id)

        return document

    async def get_document(self, document_id: uuid.UUID) -> Document | None:
        """Get a single document by ID."""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_all_documents(self) -> list[Document]:
        """Get all documents."""
        result = await self.db.execute(
            select(Document).order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_document(self, document_id: uuid.UUID) -> bool:
        """
        Delete a document and its file.
        Returns True if deleted, False if not found.
        """
        document = await self.get_document(document_id)

        if not document:
            return False

        # Delete the file from storage
        file_path = settings.DOCUMENTS_PATH / f"{document_id}_{document.filename}"
        if file_path.exists():
            file_path.unlink()

        # Delete from database
        await self.db.delete(document)

        return True

    async def get_chunk(self, chunk_id: uuid.UUID) -> Chunk | None:
        """
        Get a specific evidence chunk by ID with its parent document relationship loaded.
        """
        result = await self.db.execute(
            select(Chunk)
            .options(selectinload(Chunk.document))
            .where(Chunk.id == chunk_id)
        )
        return result.scalar_one_or_none()