# Financial Table Extraction Architecture (Sprint 4.1) — FinSight

This document details the architecture, design decisions, data contracts, and normalization mechanisms for FinSight's PDF financial table extraction pipeline.

---

## 1. Library Selection: pdfplumber (v0.11.0)

### Why pdfplumber?
For Sprint 4.1, `pdfplumber` was selected for PDF table detection and cell boundary extraction:
1. **Precise Geometric Grid Detection:** `pdfplumber` analyzes explicit line/rectangle primitives and layout coordinates in PDF streams, accurately segmenting multi-column tables.
2. **Text-within-Cell Isolation:** Extracts cell contents within spatial boundaries, preventing numbers from adjacent columns from bleeding together.
3. **No Heavy OCR Overhead:** Lightweight, pure Python/PDF parsing without requiring Tesseract or GPU dependencies.
4. **Resilience to Sparse Tables:** Reliably preserves empty cells without misaligning row lengths.

---

## 2. In-Memory Data Contract: `ExtractedTable`

Defined in `app/services/table_extractor.py`, `ExtractedTable` provides a structured, JSON-compatible in-memory representation:

```python
@dataclass
class ExtractedTable:
    table_id: str                   # e.g., "tbl_1_1" (page 1, table 1)
    document_id: str                # UUID string of parent Document
    page_number: int                # 1-indexed source physical page
    headers: list[str]              # List of column header names
    rows: list[list[str]]           # 2D grid of normalized cell values
    column_count: int               # Number of columns
    row_count: int                  # Total rows (including headers)
    title: str | None = None        # Detected title / caption
    units: str | None = None        # Detected unit scale (e.g. "millions")
    currency: str | None = None     # Detected currency ISO code (e.g. "USD")
    markdown: str = ""              # Deterministic Markdown table string
    metadata: dict[str, Any]        # Extraction diagnostic metadata
```

> **Key Architectural Invariant:** `ExtractedTable` retains the exact source `page_number` for verifiable downstream RAG citations. In Sprint 4.1, **no `Chunk` database rows are created**, preserving database isolation until the table-aware chunking sprint.

---

## 3. TableExtractorService Responsibilities

Implemented in `app/services/table_extractor.py`:

### A. Table Detection & Extraction
- Iterates page-by-page across PDF pages.
- Invokes `pdfplumber.Page.extract_tables()` to detect rectangular grid lines.
- Normalizes cell content, stripping internal line breaks into spaces while trimming outer whitespace.

### B. Header & Structure Preservation
- Pads uneven rows with empty strings (`""`) to maintain a strict rectangular matrix.
- Conservative Header Detection: Identifies row 0 as header when populated with descriptive labels and followed by data rows.
- Preserves empty and sparse cells without dropping rows or fabricating values (e.g., empty cell is `""`, never assumed to be `"0"`).

### C. Financial Fidelity & Normalization
- **Currency Detection:** Explicitly scans table text and surrounding context for currency symbols (`$`, `€`, `£`, `¥`, `USD`, `EUR`, `GBP`, `JPY`).
- **Unit Scale Detection:** Detects explicit unit declarations such as `"in millions"`, `"in thousands"`, `"in billions"` and stores the scale in metadata without mutating underlying numerical values.
- **Number & Symbol Preservation:** Strictly preserves negative numbers in parentheses (`($600.00)`), decimal values (`$1,450.75`), percentages (`15.5%`), and currency prefixes.

### D. Markdown Serialization
- Generates clean, standard Markdown table syntax with aligned column headers and delimiter rows (`| --- | --- |`).

---

## 4. Ingestion Pipeline & Worker Integration

The `process_document` task in `app/tasks/definitions.py`:
1. Executes `PDFParserService` to extract page-by-page text.
2. In-memory execution: Invokes `TableExtractorService.extract_tables_from_pdf()` for PDF files.
3. Logs table count and execution duration.
4. Transitions document status to `parsed`.

```
PDF Upload
   │
   ▼
process_document
   ├──> PDFParserService ──> ParsedDocument (Pages & Text)
   └──> TableExtractorService ──> ExtractedTable[] (Tables & Markdown)
   │
   ▼
Document.status = 'parsed'
(Zero Chunk DB records created)
```

---

## 5. Scope & Deferred Features

The following features are intentionally **NOT** implemented in Sprint 4.1:
- ❌ **Database Storage of Tables:** Table records are not inserted into `chunks` table (scheduled for Phase 5).
- ❌ **Financial Statement Classification:** Deep semantic classification of balance sheets vs cash flows (Sprint 4.2).
- ❌ **Embeddings & Vector Indexing:** No embeddings are generated for tables in this sprint.
- ❌ **RAG & Query Routing:** LLM query routing is deferred to later multi-agent phases.
