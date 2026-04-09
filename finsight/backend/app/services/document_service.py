import uuid
import aiofiles
from pathlib import Path

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.models.document import Document

settings = get_settings()


class DocumentService:
    """Service for handling document operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_file(self, file: UploadFile) -> tuple[str, int]:
        """
        Validate uploaded file type and size.
        Returns (file_extension, file_size) if valid.
        Raises HTTPException if invalid.
        """
        # Check filename exists
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )

        # Extract file extension
        file_extension = file.filename.split(".")[-1].lower()

        # Check allowed types
        if file_extension not in settings.ALLOWED_FILE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{file_extension}' not allowed. Allowed types: {settings.ALLOWED_FILE_TYPES}"
            )

        # Read file content to check size
        content = await file.read()
        file_size = len(content)

        # Check file size
        if file_size > settings.MAX_FILE_SIZE:
            max_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum allowed size of {max_mb}MB"
            )

        # Reset file position for later reading
        await file.seek(0)

        return file_extension, file_size

    async def save_file(self, file: UploadFile, document_id: uuid.UUID) -> Path:
        """
        Save uploaded file to storage.
        Returns the path where the file was saved.
        """
        # Create storage directory if it doesn't exist
        settings.DOCUMENTS_PATH.mkdir(parents=True, exist_ok=True)

        # Generate unique filename: {document_id}_{original_filename}
        safe_filename = f"{document_id}_{file.filename}"
        file_path = settings.DOCUMENTS_PATH / safe_filename

        # Save file using async I/O
        async with aiofiles.open(file_path, "wb") as out_file:
            content = await file.read()
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
        # Step 1: Validate
        file_extension, file_size = await self.validate_file(file)

        # Step 2: Create DB record
        document = await self.create_document(
            filename=file.filename,
            file_type=file_extension,
            file_size=file_size,
            title=title,
            description=description,
            source=source,
        )

        # Step 3: Save file
        await self.save_file(file, document.id)

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