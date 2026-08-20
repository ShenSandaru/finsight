"""PDF document parser service providing page-by-page text extraction and metadata parsing."""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError, FileNotDecryptedError

from app.core.exceptions import ProcessingError

logger = logging.getLogger("finsight.services.pdf_parser")


@dataclass
class ParsedPage:
    """Structured in-memory representation of a single extracted PDF page."""

    page_number: int  # 1-indexed
    text: str
    char_count: int
    is_empty: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Structured in-memory representation of an entire parsed PDF document."""

    document_id: str
    filename: str
    total_pages: int
    metadata: dict[str, Any] = field(default_factory=dict)
    pages: list[ParsedPage] = field(default_factory=list)


class PDFParserService:
    """Service responsible for extracting text and metadata from PDF files using pypdf."""

    @staticmethod
    def normalize_text(raw_text: str) -> str:
        """
        Perform conservative, safe text normalization:
        - Normalize CRLF/CR to LF
        - Convert tabs to single spaces
        - Strip excessive surrounding blank lines
        - Collapse 3+ consecutive newlines into 2
        Preserves numbers, punctuation, casing, and intra-line words.
        """
        if not raw_text:
            return ""

        # Normalize line endings
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

        # Normalize horizontal tabs to space
        text = text.replace("\t", " ")

        # Collapse excessive blank lines (more than 2 consecutive newlines -> 2)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Trim leading/trailing blank whitespace
        return text.strip()

    @staticmethod
    def extract_document_metadata(reader: PdfReader) -> dict[str, Any]:
        """Safely extract and normalize document metadata from PDF catalog."""
        metadata: dict[str, Any] = {}
        try:
            if reader.metadata:
                raw_meta = reader.metadata
                if raw_meta.title:
                    metadata["title"] = str(raw_meta.title).strip()
                if raw_meta.author:
                    metadata["author"] = str(raw_meta.author).strip()
                if raw_meta.creator:
                    metadata["creator"] = str(raw_meta.creator).strip()
                if raw_meta.producer:
                    metadata["producer"] = str(raw_meta.producer).strip()
                if raw_meta.creation_date:
                    metadata["creation_date"] = str(raw_meta.creation_date)
        except Exception as exc:
            logger.warning("Could not extract PDF metadata dictionary: %s", exc)

        return metadata

    def extract_text_and_metadata(self, file_path: Path, document_id: str = "") -> ParsedDocument:
        """
        Extract page-by-page text and document metadata from a PDF file.
        
        Args:
            file_path: Path to the target PDF file on disk.
            document_id: Optional string representation of the Document UUID.

        Returns:
            ParsedDocument containing all ParsedPages and metadata.

        Raises:
            ProcessingError: If the file is missing, encrypted, malformed, or unreadable.
        """
        if not file_path.exists():
            logger.error("PDF file not found at path: %s [document_id=%s]", file_path, document_id)
            raise ProcessingError(
                message="PDF file not found on storage disk",
                details={"file_path": str(file_path), "document_id": document_id},
            )

        try:
            reader = PdfReader(str(file_path))
        except FileNotDecryptedError as exc:
            logger.error("Encrypted PDF cannot be read without password: %s", exc)
            raise ProcessingError(
                message="PDF is encrypted/password-protected and cannot be parsed",
                details={"document_id": document_id},
            ) from exc
        except (PdfReadError, Exception) as exc:
            logger.error("Malformed or unreadable PDF: %s", exc)
            raise ProcessingError(
                message=f"Malformed or unreadable PDF document: {type(exc).__name__}",
                details={"document_id": document_id},
            ) from exc

        # Check encryption flag on reader
        if reader.is_encrypted:
            try:
                # Attempt default decrypt for empty-password encrypted PDFs
                decrypt_result = reader.decrypt("")
                if decrypt_result == 0:
                    raise ProcessingError(
                        message="PDF is encrypted and requires a password",
                        details={"document_id": document_id},
                    )
            except Exception as exc:
                logger.error("Failed to decrypt PDF: %s", exc)
                raise ProcessingError(
                    message="PDF is encrypted and cannot be opened",
                    details={"document_id": document_id},
                ) from exc

        total_pages = len(reader.pages)
        doc_metadata = self.extract_document_metadata(reader)
        parsed_pages: list[ParsedPage] = []

        logger.info(
            "Extracting %d pages from PDF '%s' [document_id=%s]",
            total_pages,
            file_path.name,
            document_id,
        )

        for idx, page in enumerate(reader.pages):
            page_number = idx + 1
            page_text = ""

            try:
                extracted = page.extract_text()
                if extracted:
                    page_text = self.normalize_text(extracted)
            except Exception as page_exc:
                logger.warning(
                    "Text extraction failed on page %d of '%s': %s (treating as empty page)",
                    page_number,
                    file_path.name,
                    page_exc,
                )
                page_text = ""

            char_count = len(page_text)
            is_empty = char_count == 0

            parsed_pages.append(
                ParsedPage(
                    page_number=page_number,
                    text=page_text,
                    char_count=char_count,
                    is_empty=is_empty,
                    metadata={"page_number": page_number},
                )
            )

        return ParsedDocument(
            document_id=document_id,
            filename=file_path.name,
            total_pages=total_pages,
            metadata=doc_metadata,
            pages=parsed_pages,
        )
