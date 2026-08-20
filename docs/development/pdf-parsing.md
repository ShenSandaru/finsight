# PDF Document Parsing Architecture (Sprint 3.1) — FinSight

This document details the architecture, design decisions, data contracts, and integration workflows for FinSight's PDF parsing service.

---

## 1. Library Selection: pypdf (v4.1.0)

### Why pypdf?
For Sprint 3.1, `pypdf` was selected as the foundational PDF text extraction and document inspection engine:
1. **Lightweight & Pure Python:** Has zero system-level C/C++ or Tesseract dependencies, keeping the Docker image minimal and portable.
2. **Deterministic Page-by-Page Extraction:** Provides fine-grained iterator access over physical PDF pages with explicit boundary preservation.
3. **Metadata & Catalog Access:** Efficiently extracts document catalog metadata (`title`, `author`, `creator`, `creation_date`) without reading full page streams upfront.
4. **Resilience & Encryption Detection:** Clear API for identifying encrypted documents, empty text streams, and invalid PDF catalog structures.

---

## 2. In-Memory Data Contracts

The parser produces structured in-memory dataclasses defined in `app/services/pdf_parser.py`:

### `ParsedPage`
Represents an individual physical PDF page:
- `page_number` (`int`): 1-indexed sequential physical page number.
- `text` (`str`): Normalized text extracted from the page.
- `char_count` (`int`): Length of `text` (`len(text)`).
- `is_empty` (`bool`): `True` if `char_count == 0` (e.g. scanned image page or blank separator).
- `metadata` (`dict[str, Any]`): Page-specific metadata (e.g., `{"page_number": N}`).

### `ParsedDocument`
Represents the entire parsed document:
- `document_id` (`str`): UUID string of the document.
- `filename` (`str`): Base filename on disk.
- `total_pages` (`int`): Total count of physical pages in the PDF.
- `metadata` (`dict[str, Any]`): Document-level metadata extracted from PDF catalog.
- `pages` (`list[ParsedPage]`): Sequential list of all pages in physical order.

> **Important:** No database tables are created for `ParsedPage` or `ParsedDocument` in Sprint 3.1. These structures serve as the in-memory contract for subsequent chunking and embedding pipelines.

---

## 3. PDFParserService Responsibilities

Implemented in `app/services/pdf_parser.py`:
1. **File Path Verification:** Validates that the target file exists on storage disk and is accessible.
2. **Integrity & Encryption Guards:** Catches encrypted/password-protected PDFs and malformed binary files, raising standardized `ProcessingError`.
3. **Page Iteration & Extraction:** Iterates through every physical page without dropping empty pages or losing boundaries.
4. **Lightweight Text Normalization:**
   - Normalizes CRLF (`\r\n`) and CR (`\r`) to LF (`\n`).
   - Converts horizontal tabs (`\t`) to single spaces.
   - Collapses 3+ consecutive newlines into 2 (`\n\n`) to preserve paragraph structure without unbounded whitespace.
   - Trims outer leading/trailing blank whitespace.
   - *Preserves numbers, punctuation, casing, and intra-line word boundaries intact.*
5. **Metadata Extraction:** Extracts standard PDF metadata (`title`, `author`, `creator`, `producer`, `creation_date`) into JSON-safe dictionaries without hallucinating missing fields.

---

## 4. Ingestion Pipeline & Worker Integration

The asynchronous document processing workflow transitions through the following stages:

```
1. Client POST /api/v1/documents/upload
   │
   ▼
2. Validation & Save to Disk -> Status: 'pending' (DB Transaction Committed)
   │
   ▼
3. Enqueue 'process_document' to Redis ('finsight_tasks')
   │
   ▼
4. ARQ Worker consumes task
   │
   ▼
5. State Transition 1: Status = 'processing'
   │
   ▼
6. PDFParserService.extract_text_and_metadata(file_path)
   ├── [Success] ──> Update Document.total_pages & title
   │                 State Transition 2: Status = 'parsed', processing_error = None
   │
   └── [Failure] ──> Catch ProcessingError / Exception
                     State Transition 2: Status = 'failed', processing_error = '<safe message>'
```

### Path Resolution Convention
Resolves files using `DocumentService`'s standard storage path:
`settings.DOCUMENTS_PATH / f"{doc_uuid}_{document.filename}"`

### Idempotency
`process_document` strictly checks that `document.status == "pending"`. If the document is already `processing`, `parsed`, or `failed`, duplicate executions are safely skipped without side effects.

---

## 5. Non-PDF Files (TXT / CSV)

- Upload of `.txt` and `.csv` files is supported at the API layer.
- In Sprint 3.1, TXT and CSV parsing is intentionally deferred.
- When a `.txt` or `.csv` task is consumed, the worker sets `status = "failed"` with `processing_error = "TXT/CSV parsing is not implemented yet"`, avoiding tasks becoming stuck in `processing`.

---

## 6. Intentionally Deferred Features (Future Sprints)

The following components are explicitly **NOT** part of Sprint 3.1:
- ❌ **Table Extraction & Detection:** Structured financial tables (Balance Sheets, Income Statements) will be extracted in Phase 4.
- ❌ **OCR / Scanned PDF Recognition:** Handled in future multimodal/OCR phases.
- ❌ **Chunking:** Chunk generation and database persistence in `chunks` table will be implemented in Phase 5.
- ❌ **Embeddings & Vector Search:** Embedding generation and pgvector similarity querying are scheduled for Phase 6.
- ❌ **RAG & Agent Workflows:** Multi-agent LangGraph orchestrator is scheduled for subsequent phases.
