"""CSV document parser service providing safe decoding, tabular preservation, and structured parsing."""

import csv
import io
import logging
from pathlib import Path
from typing import Any

from app.core.exceptions import ProcessingError
from app.services.pdf_parser import ParsedPage, ParsedDocument
from app.services.text_parser import TextParserService

logger = logging.getLogger("finsight.services.csv_parser")


class CSVParserService:
    """Service responsible for reading, decoding, and parsing CSV documents while preserving structure."""

    def extract_text_and_metadata(self, file_path: Path, document_id: str = "") -> ParsedDocument:
        """
        Parse a CSV file into a standardized ParsedDocument.
        Convention: CSV files are represented as 1 logical page with structured tabular metadata.
        
        Args:
            file_path: Path to the target CSV file on disk.
            document_id: Optional string representation of the Document UUID.

        Returns:
            ParsedDocument containing exactly 1 logical ParsedPage and structured CSV metadata.

        Raises:
            ProcessingError: If the file is missing, unreadable, corrupt, or contains invalid encoding/syntax.
        """
        if not file_path.exists():
            logger.error("CSV file not found at path: %s [document_id=%s]", file_path, document_id)
            raise ProcessingError(
                message="CSV file not found on storage disk",
                details={"file_path": str(file_path), "document_id": document_id},
            )

        try:
            raw_bytes = file_path.read_bytes()
        except Exception as exc:
            logger.error("Error reading CSV file %s: %s", file_path, exc)
            raise ProcessingError(
                message=f"Failed to read CSV file from disk: {type(exc).__name__}",
                details={"document_id": document_id},
            ) from exc

        # Safe decoding using TextParserService's multi-encoding cascade
        raw_text, detected_encoding = TextParserService.decode_file_bytes(raw_bytes, file_path)

        if not raw_text.strip():
            # Handle completely empty CSV
            return ParsedDocument(
                document_id=document_id,
                filename=file_path.name,
                total_pages=1,
                metadata={
                    "format": "csv",
                    "encoding": detected_encoding,
                    "row_count": 0,
                    "column_count": 0,
                    "column_names": [],
                },
                pages=[
                    ParsedPage(
                        page_number=1,
                        text="",
                        char_count=0,
                        is_empty=True,
                        metadata={"page_number": 1, "format": "csv", "row_count": 0, "column_count": 0},
                    )
                ],
            )

        # Parse CSV rows with standard csv.reader
        try:
            reader = csv.reader(io.StringIO(raw_text))
            rows: list[list[str]] = list(reader)
        except Exception as exc:
            logger.error("CSV parsing failed on %s: %s", file_path, exc)
            raise ProcessingError(
                message=f"Malformed or invalid CSV document: {type(exc).__name__}",
                details={"document_id": document_id},
            ) from exc

        if not rows:
            return ParsedDocument(
                document_id=document_id,
                filename=file_path.name,
                total_pages=1,
                metadata={
                    "format": "csv",
                    "encoding": detected_encoding,
                    "row_count": 0,
                    "column_count": 0,
                    "column_names": [],
                },
                pages=[
                    ParsedPage(
                        page_number=1,
                        text="",
                        char_count=0,
                        is_empty=True,
                        metadata={"page_number": 1, "format": "csv", "row_count": 0, "column_count": 0},
                    )
                ],
            )

        # Extract column names from header (first row) and compute column count
        column_names = [col.strip() for col in rows[0]]
        column_count = len(column_names)
        row_count = len(rows)

        # Generate a clean, stable tabular representation (CSV text format)
        # Using standard csv writer buffer to ensure consistent normalization
        text_buf = io.StringIO()
        writer = csv.writer(text_buf, lineterminator="\n")
        for row in rows:
            writer.writerow(row)
        table_text = text_buf.getvalue().strip()

        doc_metadata: dict[str, Any] = {
            "format": "csv",
            "encoding": detected_encoding,
            "row_count": row_count,
            "column_count": column_count,
            "column_names": column_names,
            "raw_byte_size": len(raw_bytes),
        }

        page_metadata: dict[str, Any] = {
            "page_number": 1,
            "format": "csv",
            "row_count": row_count,
            "column_count": column_count,
            "column_names": column_names,
            "rows": rows[:100],  # Cache sample rows for inspection up to 100 rows
        }

        logical_page = ParsedPage(
            page_number=1,
            text=table_text,
            char_count=len(table_text),
            is_empty=len(table_text) == 0,
            metadata=page_metadata,
        )

        return ParsedDocument(
            document_id=document_id,
            filename=file_path.name,
            total_pages=1,  # Documented convention: CSV is 1 logical page
            metadata=doc_metadata,
            pages=[logical_page],
        )
