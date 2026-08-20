# Document Parsing Architecture (PDF, TXT, CSV) — FinSight

This document details the architecture, design decisions, data contracts, and integration workflows for FinSight's document parsing services across PDF, Plain Text (.txt), and CSV formats, including conservative boilerplate filtering.

---

## 1. Parsers & Format Handlers

FinSight implements a modular, format-specific parser service layer producing a unified in-memory representation:

```
                  ┌──────────────────────┐
                  │ POST /documents/upload│
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │     Redis / ARQ      │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │   process_document   │
                  └──────────┬───────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  PDF Parser  │      │  Text Parser │      │  CSV Parser  │
│(pypdf v4.1.0)│      │(.txt handler)│      │(Python csv)  │
└──────┬───────┘      └──────┬───────┘      └──────┬───────┘
       │                     │                     │
       └─────────────────────┼─────────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    ParsedDocument    │
                  │ (Unified In-Memory)  │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Document.total_pages │
                  │  status = 'parsed'   │
                  └──────────────────────┘
```

---

## 2. In-Memory Data Contracts

All parsers output the shared dataclass structures defined in `app/services/pdf_parser.py`:

### `ParsedPage`
Represents an individual extracted page (or logical page):
- `page_number` (`int`): 1-indexed sequential page number.
- `text` (`str`): Normalized text extracted from the page.
- `char_count` (`int`): Character length (`len(text)`).
- `is_empty` (`bool`): `True` if `char_count == 0`.
- `metadata` (`dict[str, Any]`): Page-specific metadata (e.g. format, column names, tabular row slices).

### `ParsedDocument`
Represents the entire parsed document:
- `document_id` (`str`): UUID string of the document.
- `filename` (`str`): Stored filename.
- `total_pages` (`int`): Total physical pages (PDF) or logical pages (TXT/CSV).
- `metadata` (`dict[str, Any]`): Document-level metadata.
- `pages` (`list[ParsedPage]`): Sequential list of `ParsedPage` items.

---

## 3. Format Parser Specifications

### A. PDFParserService (`app/services/pdf_parser.py`)
- **Engine:** `pypdf` (v4.1.0).
- **Page Extraction:** Iterates through physical PDF pages, preserving 1-indexed page boundaries and tracking empty/scanned pages.
- **Normalization:** Converts CRLF/CR to LF, converts horizontal tabs to spaces, collapses 3+ newlines to 2, and strips outer whitespace.
- **Metadata Extraction:** Extracts `title`, `author`, `creator`, `producer`, and `creation_date` from the PDF document catalog.
- **Boilerplate Filtering:** Applies conservative repeated header/footer and page-number filtering across multi-page documents ($\ge 3$ pages).

### B. TextParserService (`app/services/text_parser.py`)
- **Format:** Plain text (`.txt`).
- **Logical Page Convention:** Text files have no physical pages; they are represented as **1 logical page** (`total_pages = 1`, `pages = [ParsedPage(page_number=1, ...)]`).
- **Decoding Strategy:** Multi-encoding cascade checking UTF-8 with BOM (`utf-8-sig`), standard `utf-8`, and `latin-1`. Explicitly rejects binary null bytes (`\x00`).
- **Metadata:** `{ "format": "txt", "encoding": "...", "character_count": ..., "raw_byte_size": ... }`.

### C. CSVParserService (`app/services/csv_parser.py`)
- **Format:** Comma-Separated Values (`.csv`).
- **Logical Page Convention:** CSV files are represented as **1 logical page** (`total_pages = 1`).
- **Tabular Preservation:** Uses Python's standard `csv.reader` to preserve rows, columns, quoted strings, and embedded commas.
- **Metadata:**
  - Document metadata: `{ "format": "csv", "encoding": "...", "column_names": [...], "column_count": N, "row_count": M }`.
  - Page metadata: `{ "page_number": 1, "format": "csv", "column_names": [...], "rows": [...] }`.
- **Text Representation:** Normalizes tabular rows into clean, uniform CSV text lines suitable for future chunking.

---

## 4. Conservative Boilerplate Filtering Algorithm

Implemented in `PDFParserService.filter_repeated_boilerplate`:

1. **Activation Threshold:** Only runs on multi-page documents with $\ge 3$ non-empty pages.
2. **Boundary Candidate Inspection:** Inspects only the top 2 lines (header candidates) and bottom 2 lines (footer candidates) of each page.
3. **Repetition Frequency:** Identifies non-numeric strings occurring in $\ge 75\%$ of pages across at least 3 distinct pages.
4. **Financial & Numeric Guardrails:** Explicitly protects numeric amounts, currency values (`$`, `€`, `£`, `100.50`), years (`2025`), and critical accounting headings (`Revenue`, `Total Assets`, `Net Income`, `Operating Expense`, `Cash Flow`) from being deleted.
5. **Page Number Regex:** Strips explicit page numbers at the top/bottom matching patterns like `Page X of Y`, `Page X`, or `- X -`.

---

## 5. Ingestion Pipeline & Worker Integration

The `process_document` task in `app/tasks/definitions.py`:
1. Checks idempotency: skips execution if `document.status != "pending"`.
2. Transitions: `pending` $\rightarrow$ `processing` $\rightarrow$ `parsed` (or `failed`).
3. Dispatches to `PDFParserService`, `TextParserService`, or `CSVParserService` based on `document.file_type`.
4. Sets `Document.total_pages` ($N$ for PDF, $1$ for TXT/CSV).
5. Populates `Document.title` from document metadata if not already specified.
6. Cleans up `Document.processing_error` upon success or sets concise diagnostic upon failure.

---

## 6. Intentionally Deferred Features (Future Phases)

- ❌ **Financial Table Classification:** Automatic classification of Balance Sheets, Income Statements, and Cash Flow tables (Phase 4).
- ❌ **Markdown Table Normalization:** Markdown syntax table generation from complex PDF table layouts (Phase 4).
- ❌ **Chunking:** Chunk generation and database persistence in `chunks` table (Phase 5).
- ❌ **Embeddings & Vector Search:** pgvector embeddings and similarity search (Phase 6).
- ❌ **Multi-Agent RAG:** LangGraph orchestration (Phase 7+).
