"""Table-aware document chunking service preserving page boundaries and financial table semantics."""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.services.pdf_parser import ParsedDocument
from app.services.table_extractor import ExtractedTable

logger = logging.getLogger("finsight.services.chunker")
settings = get_settings()


@dataclass
class ChunkData:
    """Internal structured data contract representing a single document chunk prior to database persistence."""

    content: str
    chunk_type: str  # "text" or "table"
    chunk_index: int  # 0-indexed sequential position within document
    page_number: int | None  # 1-indexed source physical or logical page
    metadata: dict[str, Any] = field(default_factory=dict)


class TableAwareChunkerService:
    """Service responsible for splitting text into coherent chunks and preserving financial table structures."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        self.chunk_size = chunk_size or settings.DEFAULT_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP

    def split_text(self, text: str) -> list[str]:
        """
        Deterministically split text into chunks using recursive separator hierarchy:
        1. Paragraph boundaries ('\\n\\n')
        2. Line boundaries ('\\n')
        3. Sentence boundaries ('. ')
        4. Word boundaries (' ')
        5. Hard character fallback
        """
        clean_text = text.strip()
        if not clean_text:
            return []

        if len(clean_text) <= self.chunk_size:
            return [clean_text]

        return self._recursive_split(clean_text, ["\n\n", "\n", ". ", " "])

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        """Recursive chunk splitting helper with overlap window."""
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text.strip()] if text.strip() else []

        if not separators:
            # Fallback to hard character slicing if no separators remain
            chunks = []
            start = 0
            while start < len(text):
                end = start + self.chunk_size
                chunk = text[start:end].strip()
                if chunk:
                    chunks.append(chunk)
                if end >= len(text):
                    break
                start = max(start + 1, end - self.chunk_overlap)
            return chunks

        sep = separators[0]
        remaining_separators = separators[1:]

        splits = text.split(sep)
        chunks: list[str] = []
        current_piece = ""

        for part in splits:
            part_str = part.strip()
            if not part_str:
                continue

            candidate = f"{current_piece}{sep}{part_str}" if current_piece else part_str

            if len(candidate) <= self.chunk_size:
                current_piece = candidate
            else:
                if current_piece:
                    chunks.append(current_piece)
                    # Compute overlap from end of current_piece
                    if self.chunk_overlap > 0 and len(current_piece) > self.chunk_overlap:
                        overlap_tail = current_piece[-self.chunk_overlap :]
                        current_piece = f"{overlap_tail}{sep}{part_str}" if len(overlap_tail) + len(sep) + len(part_str) <= self.chunk_size else part_str
                    else:
                        current_piece = part_str
                else:
                    # Single piece is larger than chunk_size -> recurse with finer separator
                    sub_chunks = self._recursive_split(part_str, remaining_separators)
                    chunks.extend(sub_chunks)
                    current_piece = ""

        if current_piece and current_piece.strip():
            chunks.append(current_piece.strip())

        return chunks

    def create_chunks(
        self,
        parsed_doc: ParsedDocument,
        tables: list[ExtractedTable] | None = None,
    ) -> list[ChunkData]:
        """
        Transform a ParsedDocument and extracted tables into a sequence of ChunkData objects.

        Ordering rule:
        Per page:
          1. Page text chunks (in reading order)
          2. Page table chunks (in extraction order)
        Sequential chunk_index (0, 1, 2, ...) assigned across the document.

        Empty Page rule:
        If a page has empty text and no tables, 0 chunks are generated for that page.
        """
        tables = tables or []
        doc_chunks: list[ChunkData] = []
        chunk_index = 0

        # Index tables by page_number
        tables_by_page: dict[int, list[ExtractedTable]] = {}
        for tbl in tables:
            tables_by_page.setdefault(tbl.page_number, []).append(tbl)

        doc_format = parsed_doc.metadata.get("format", "pdf")

        if doc_format == "csv":
            # Structured CSV Chunking
            return self._create_csv_chunks(parsed_doc)

        for page in parsed_doc.pages:
            page_num = page.page_number
            page_text = page.text.strip() if page.text else ""

            # 1. Text chunks for page
            if page_text:
                text_splits = self.split_text(page_text)
                for split in text_splits:
                    meta = {
                        "source_type": "text",
                        "page_number": page_num,
                        "char_count": len(split),
                        "filename": parsed_doc.filename,
                    }
                    doc_chunks.append(
                        ChunkData(
                            content=split,
                            chunk_type="text",
                            chunk_index=chunk_index,
                            page_number=page_num,
                            metadata=meta,
                        )
                    )
                    chunk_index += 1

            # 2. Table chunks for page
            page_tables = tables_by_page.get(page_num, [])
            for tbl in page_tables:
                table_meta = self._serialize_table_metadata(tbl, parsed_doc.filename)
                doc_chunks.append(
                    ChunkData(
                        content=tbl.markdown,
                        chunk_type="table",
                        chunk_index=chunk_index,
                        page_number=page_num,
                        metadata=table_meta,
                    )
                )
                chunk_index += 1

        logger.info(
            "Created %d chunks (%d text, %d table) for document '%s'",
            len(doc_chunks),
            sum(1 for c in doc_chunks if c.chunk_type == "text"),
            sum(1 for c in doc_chunks if c.chunk_type == "table"),
            parsed_doc.filename,
        )
        return doc_chunks

    def _create_csv_chunks(self, parsed_doc: ParsedDocument) -> list[ChunkData]:
        """Create structured chunks for CSV documents while preserving tabular header line."""
        chunks: list[ChunkData] = []
        chunk_index = 0

        for page in parsed_doc.pages:
            raw_text = page.text.strip() if page.text else ""
            if not raw_text:
                continue

            lines = [l for l in raw_text.split("\n") if l.strip()]
            if not lines:
                continue

            header_line = lines[0]
            data_lines = lines[1:]

            if len(raw_text) <= self.chunk_size or not data_lines:
                meta = {
                    "source_type": "table",
                    "format": "csv",
                    "page_number": 1,
                    "row_count": len(lines),
                    "filename": parsed_doc.filename,
                }
                chunks.append(
                    ChunkData(
                        content=raw_text,
                        chunk_type="table",
                        chunk_index=chunk_index,
                        page_number=1,
                        metadata=meta,
                    )
                )
                chunk_index += 1
            else:
                # Split large CSV rows, repeating header line on each chunk
                current_chunk_lines = [header_line]
                current_len = len(header_line)

                for line in data_lines:
                    line_len = len(line) + 1  # newline
                    if current_len + line_len <= self.chunk_size:
                        current_chunk_lines.append(line)
                        current_len += line_len
                    else:
                        if len(current_chunk_lines) > 1:
                            chunk_content = "\n".join(current_chunk_lines)
                            chunks.append(
                                ChunkData(
                                    content=chunk_content,
                                    chunk_type="table",
                                    chunk_index=chunk_index,
                                    page_number=1,
                                    metadata={
                                        "source_type": "table",
                                        "format": "csv",
                                        "page_number": 1,
                                        "filename": parsed_doc.filename,
                                    },
                                )
                            )
                            chunk_index += 1
                        current_chunk_lines = [header_line, line]
                        current_len = len(header_line) + 1 + len(line)

                if len(current_chunk_lines) > 1:
                    chunk_content = "\n".join(current_chunk_lines)
                    chunks.append(
                        ChunkData(
                            content=chunk_content,
                            chunk_type="table",
                            chunk_index=chunk_index,
                            page_number=1,
                            metadata={
                                "source_type": "table",
                                "format": "csv",
                                "page_number": 1,
                                "filename": parsed_doc.filename,
                            },
                        )
                    )
                    chunk_index += 1

        return chunks

    @staticmethod
    def _serialize_table_metadata(tbl: ExtractedTable, filename: str) -> dict[str, Any]:
        """Convert ExtractedTable and FinancialTableSemantics into a clean JSON-serializable dictionary."""
        meta: dict[str, Any] = {
            "source_type": "table",
            "table_id": tbl.table_id,
            "page_number": tbl.page_number,
            "filename": filename,
            "title": tbl.title,
            "currency": tbl.currency,
            "units": tbl.units,
            "column_count": tbl.column_count,
            "row_count": tbl.row_count,
        }

        if tbl.semantics:
            meta["statement_type"] = tbl.semantics.statement_type
            meta["confidence"] = tbl.semantics.confidence
            meta["period_type"] = tbl.semantics.period_type
            meta["fiscal_periods"] = tbl.semantics.fiscal_periods
            meta["period_context"] = tbl.semantics.period_context
            meta["key_metrics"] = tbl.semantics.key_metrics
            meta["has_year_columns"] = tbl.semantics.has_year_columns
            meta["has_quarter_columns"] = tbl.semantics.has_quarter_columns
            if tbl.semantics.currency and not meta.get("currency"):
                meta["currency"] = tbl.semantics.currency
            if tbl.semantics.units and not meta.get("units"):
                meta["units"] = tbl.semantics.units

        return meta
