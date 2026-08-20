"""Plain text (.txt) document parser service providing safe decoding and structured parsing."""

import logging
from pathlib import Path
from typing import Any

from app.core.exceptions import ProcessingError
from app.services.pdf_parser import ParsedPage, ParsedDocument, PDFParserService

logger = logging.getLogger("finsight.services.text_parser")


class TextParserService:
    """Service responsible for reading, decoding, and parsing plain text (.txt) documents."""

    # Prioritize utf-8-sig before standard utf-8 so BOMs are detected and stripped cleanly
    SUPPORTED_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")

    @classmethod
    def decode_file_bytes(cls, raw_bytes: bytes, file_path: Path) -> tuple[str, str]:
        """
        Safely decode raw bytes across supported encodings.
        Returns tuple of (decoded_text, detected_encoding).
        Raises ProcessingError if binary/null bytes detected or decoding fails.
        """
        # Guard against null bytes / binary content
        if b"\x00" in raw_bytes:
            logger.error("Binary null bytes detected in text file: %s", file_path)
            raise ProcessingError(
                message="Text file contains unsupported binary null bytes",
                details={"file_path": str(file_path)},
            )

        # Check for explicit UTF-8 BOM prefix
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            try:
                return raw_bytes.decode("utf-8-sig"), "utf-8-sig"
            except UnicodeDecodeError:
                pass

        for encoding in ("utf-8", "latin-1"):
            try:
                text = raw_bytes.decode(encoding)
                return text, encoding
            except UnicodeDecodeError:
                continue

        logger.error("Failed to decode text file across encodings %s: %s", cls.SUPPORTED_ENCODINGS, file_path)
        raise ProcessingError(
            message="Unable to decode text document with supported encodings (UTF-8, Latin-1)",
            details={"file_path": str(file_path)},
        )

    def extract_text_and_metadata(self, file_path: Path, document_id: str = "") -> ParsedDocument:
        """
        Parse a plain text (.txt) file into a standardized ParsedDocument.
        Convention: TXT files have no physical PDF pages; they are represented as 1 logical page.
        
        Args:
            file_path: Path to the target TXT file on disk.
            document_id: Optional string representation of the Document UUID.

        Returns:
            ParsedDocument containing exactly 1 logical ParsedPage and document metadata.

        Raises:
            ProcessingError: If the file is missing, unreadable, corrupt, or contains invalid encoding.
        """
        if not file_path.exists():
            logger.error("TXT file not found at path: %s [document_id=%s]", file_path, document_id)
            raise ProcessingError(
                message="TXT file not found on storage disk",
                details={"file_path": str(file_path), "document_id": document_id},
            )

        try:
            raw_bytes = file_path.read_bytes()
        except Exception as exc:
            logger.error("Error reading TXT file %s: %s", file_path, exc)
            raise ProcessingError(
                message=f"Failed to read TXT file from disk: {type(exc).__name__}",
                details={"document_id": document_id},
            ) from exc

        # Decode raw bytes safely
        raw_text, detected_encoding = self.decode_file_bytes(raw_bytes, file_path)

        # Apply conservative text normalization (CRLF -> LF, tabs -> spaces, collapse 3+ newlines)
        normalized_text = PDFParserService.normalize_text(raw_text)
        char_count = len(normalized_text)
        is_empty = char_count == 0

        # Document metadata
        doc_metadata: dict[str, Any] = {
            "format": "txt",
            "encoding": detected_encoding,
            "character_count": char_count,
            "raw_byte_size": len(raw_bytes),
        }

        # Logical page representation (Page 1)
        logical_page = ParsedPage(
            page_number=1,
            text=normalized_text,
            char_count=char_count,
            is_empty=is_empty,
            metadata={"page_number": 1, "format": "txt"},
        )

        return ParsedDocument(
            document_id=document_id,
            filename=file_path.name,
            total_pages=1,  # Documented convention: TXT is 1 logical page
            metadata=doc_metadata,
            pages=[logical_page],
        )
