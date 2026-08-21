"""Financial table detection, extraction, and structured normalization service using pdfplumber."""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber

from app.core.exceptions import ProcessingError
from app.services.table_semantics import FinancialTableSemantics

logger = logging.getLogger("finsight.services.table_extractor")


@dataclass
class ExtractedTable:
    """Structured in-memory representation of an extracted PDF table."""

    table_id: str
    document_id: str
    page_number: int  # 1-indexed source physical page
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    column_count: int = 0
    row_count: int = 0
    title: str | None = None
    units: str | None = None
    currency: str | None = None
    markdown: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    semantics: FinancialTableSemantics | None = None


class TableExtractorService:
    """Service responsible for detecting, extracting, and normalizing tables from PDF documents."""

    # Explicit currency symbols and ISO codes
    CURRENCY_PATTERNS = {
        "$": "USD",
        "USD": "USD",
        "€": "EUR",
        "EUR": "EUR",
        "£": "GBP",
        "GBP": "GBP",
        "¥": "JPY",
        "JPY": "JPY",
    }

    # Explicit unit scale patterns
    UNIT_PATTERNS = [
        (re.compile(r"\b(?:in\s+billions?|\$\s*in\s+billions?|\(in\s+billions?\))\b", re.IGNORECASE), "billions"),
        (re.compile(r"\b(?:in\s+millions?|\$\s*in\s+millions?|\(in\s+millions?\))\b", re.IGNORECASE), "millions"),
        (re.compile(r"\b(?:in\s+thousands?|\$\s*in\s+thousands?|\(in\s+thousands?\))\b", re.IGNORECASE), "thousands"),
    ]

    # Known financial statement header patterns for title detection
    TITLE_CANDIDATE_PATTERNS = [
        re.compile(r"Consolidated\s+Statements?\s+of\s+(?:Operations|Income|Earnings|Cash\s+Flows|Comprehensive\s+Income)", re.IGNORECASE),
        re.compile(r"Consolidated\s+Balance\s+Sheets?", re.IGNORECASE),
        re.compile(r"Statements?\s+of\s+(?:Operations|Income|Cash\s+Flows|Financial\s+Position)", re.IGNORECASE),
        re.compile(r"Balance\s+Sheets?", re.IGNORECASE),
        re.compile(r"Income\s+Statements?", re.IGNORECASE),
        re.compile(r"Cash\s+Flows?", re.IGNORECASE),
    ]

    @staticmethod
    def normalize_cell(cell: Any) -> str:
        """
        Normalize table cell content:
        - Handle None/empty values -> ""
        - Normalize internal linebreaks to single spaces
        - Preserve financial symbols, parentheses, negative signs, decimals, percentages
        - Strip excessive surrounding whitespace
        """
        if cell is None:
            return ""
        text = str(cell)
        # Normalize internal line breaks within cell
        text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
        # Collapse multiple spaces
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    @classmethod
    def detect_currency(cls, text_block: str, rows: list[list[str]]) -> str | None:
        """Detect currency only when explicit symbol or currency code is present."""
        # Search nearby context block
        for symbol, code in cls.CURRENCY_PATTERNS.items():
            if symbol in text_block:
                return code
        # Search cell content
        for row in rows:
            for cell in row:
                for symbol, code in cls.CURRENCY_PATTERNS.items():
                    if symbol in cell:
                        return code
        return None

    @classmethod
    def detect_units(cls, text_block: str, rows: list[list[str]]) -> str | None:
        """Detect explicit unit scaling (e.g. millions, thousands, billions)."""
        # Search nearby context block
        for pattern, unit_name in cls.UNIT_PATTERNS:
            if pattern.search(text_block):
                return unit_name
        # Search in first 2 rows (header or subheader area)
        for row in rows[:2]:
            row_str = " ".join(row)
            for pattern, unit_name in cls.UNIT_PATTERNS:
                if pattern.search(row_str):
                    return unit_name
        return None

    @classmethod
    def detect_table_title(cls, page_text_above: str) -> str | None:
        """Extract nearby table title/caption if confidently identified above the table."""
        if not page_text_above:
            return None
        lines = [l.strip() for l in page_text_above.split("\n") if l.strip()]
        for line in lines:
            for pattern in cls.TITLE_CANDIDATE_PATTERNS:
                match = pattern.search(line)
                if match:
                    return match.group(0).strip()
        return None

    @staticmethod
    def generate_markdown(headers: list[str], rows: list[list[str]]) -> str:
        """
        Generate a clean, deterministic Markdown representation of the table.
        """
        if not headers and not rows:
            return ""

        # Determine column count
        col_count = len(headers) if headers else (max(len(r) for r in rows) if rows else 0)
        if col_count == 0:
            return ""

        # Ensure headers have matching column length
        clean_headers = [h.replace("|", "\\|") for h in headers] if headers else [f"Col {i+1}" for i in range(col_count)]
        if len(clean_headers) < col_count:
            clean_headers.extend([""] * (col_count - len(clean_headers)))

        md_lines = [
            "| " + " | ".join(clean_headers) + " |",
            "| " + " | ".join(["---"] * col_count) + " |",
        ]

        for row in rows:
            clean_row = [c.replace("|", "\\|") for c in row]
            if len(clean_row) < col_count:
                clean_row.extend([""] * (col_count - len(clean_row)))
            elif len(clean_row) > col_count:
                clean_row = clean_row[:col_count]
            md_lines.append("| " + " | ".join(clean_row) + " |")

        return "\n".join(md_lines)

    def extract_tables_from_pdf(self, file_path: Path, document_id: str = "") -> list[ExtractedTable]:
        """
        Extract all tables page-by-page from a PDF file using pdfplumber.
        
        Args:
            file_path: Path to target PDF file on disk.
            document_id: Optional Document UUID string.

        Returns:
            List of ExtractedTable dataclass objects preserving page numbers and tabular structure.

        Raises:
            ProcessingError: If the file is missing or completely unreadable.
        """
        if not file_path.exists():
            logger.error("PDF file not found for table extraction: %s [document_id=%s]", file_path, document_id)
            raise ProcessingError(
                message="PDF file not found on storage disk",
                details={"file_path": str(file_path), "document_id": document_id},
            )

        extracted_tables: list[ExtractedTable] = []

        try:
            with pdfplumber.open(str(file_path)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_num = page_idx + 1

                    try:
                        # Extract tables using pdfplumber's default table finder
                        raw_tables = page.extract_tables()
                        if not raw_tables:
                            continue

                        page_text = page.extract_text() or ""

                        for t_idx, raw_table in enumerate(raw_tables):
                            if not raw_table or len(raw_table) == 0:
                                continue

                            # Normalize all cells
                            normalized_rows: list[list[str]] = []
                            for row in raw_table:
                                if row is None:
                                    continue
                                norm_row = [self.normalize_cell(cell) for cell in row]
                                # Discard entirely empty rows
                                if any(len(c) > 0 for c in norm_row):
                                    normalized_rows.append(norm_row)

                            if not normalized_rows:
                                continue

                            # Max column length across rows
                            max_cols = max(len(r) for r in normalized_rows)

                            # Pad uneven rows with empty string
                            for r in normalized_rows:
                                if len(r) < max_cols:
                                    r.extend([""] * (max_cols - len(r)))

                            # Conservative Header Detection
                            # Treat row 0 as header if it has text and there are subsequent data rows
                            has_header = False
                            headers: list[str] = []
                            data_rows: list[list[str]] = []

                            if len(normalized_rows) >= 2:
                                first_row = normalized_rows[0]
                                # If at least half the columns in first row are populated, assume header
                                non_empty_headers = sum(1 for c in first_row if c)
                                if non_empty_headers >= max(1, max_cols // 2):
                                    has_header = True
                                    headers = first_row
                                    data_rows = normalized_rows[1:]
                                else:
                                    headers = [f"Col {i+1}" for i in range(max_cols)]
                                    data_rows = normalized_rows
                            else:
                                headers = [f"Col {i+1}" for i in range(max_cols)]
                                data_rows = normalized_rows

                            # Context extraction for metadata/title
                            title = self.detect_table_title(page_text)
                            currency = self.detect_currency(page_text, normalized_rows)
                            units = self.detect_units(page_text, normalized_rows)

                            # Generate Markdown
                            md_repr = self.generate_markdown(headers, data_rows)

                            table_id = f"tbl_{page_num}_{t_idx+1}"
                            table_obj = ExtractedTable(
                                table_id=table_id,
                                document_id=document_id,
                                page_number=page_num,
                                headers=headers,
                                rows=data_rows,
                                column_count=max_cols,
                                row_count=len(normalized_rows),
                                title=title,
                                units=units,
                                currency=currency,
                                markdown=md_repr,
                                metadata={
                                    "has_header": has_header,
                                    "page_number": page_num,
                                    "table_index": t_idx + 1,
                                    "raw_row_count": len(raw_table),
                                    "format": "table",
                                },
                            )
                            extracted_tables.append(table_obj)

                    except Exception as page_exc:
                        logger.warning(
                            "Error extracting tables on page %d of %s: %s (continuing with remaining pages)",
                            page_num,
                            file_path.name,
                            page_exc,
                        )
                        continue

        except Exception as exc:
            logger.error("Failed to open or parse PDF tables from %s: %s", file_path, exc)
            raise ProcessingError(
                message=f"Malformed or unreadable PDF for table extraction: {type(exc).__name__}",
                details={"document_id": document_id},
            ) from exc

        logger.info(
            "Extracted %d tables from '%s' [document_id=%s]",
            len(extracted_tables),
            file_path.name,
            document_id,
        )
        return extracted_tables
