# Sprint 5.1 — Table-Aware Chunking Foundation & Chunk Persistence

## 1. Overview & Architectural Position

Sprint 5.1 introduces the deterministic, table-aware document chunking foundation (`TableAwareChunkerService`) and transactional PostgreSQL chunk persistence pipeline for FinSight.

```text
PDF / TXT / CSV
       ↓
Parser Services (PDFParserService, TextParserService, CSVParserService)
       ↓
ParsedDocument
       ↓
TableExtractorService (PDF only)
       ↓
FinancialTableSemanticService (PDF only)
       ↓
TableAwareChunkerService (Transforms ParsedDocument + Tables into ChunkData[])
       ↓
PostgreSQL Database Persistence (chunks table, embedding = NULL)
```

---

## 2. Chunk Data Contract (`ChunkData`)

Located in [`backend/app/services/chunker.py`](file:///d:/Portfolio%20soft%20projects/finsight/finsight/backend/app/services/chunker.py):

```python
@dataclass
class ChunkData:
    content: str
    chunk_type: str                   # "text" or "table"
    chunk_index: int                  # 0-indexed sequential position within document
    page_number: int | None           # 1-indexed source physical or logical page
    metadata: dict[str, Any]          # JSON-serializable diagnostic & semantic dictionary
```

Allowed `chunk_type` values:
- `"text"`: Narrative chunks split by paragraph, line, and sentence boundaries.
- `"table"`: Structured table chunks containing Markdown tables.

---

## 3. Text Chunking Algorithm

- **Hierarchy:** Recursive separator splitting:
  1. Paragraph boundaries (`\n\n`)
  2. Line boundaries (`\n`)
  3. Sentence boundaries (`. `)
  4. Word boundaries (` `)
  5. Character fallback
- **Configurable Boundaries:**
  - `DEFAULT_CHUNK_SIZE = 1200` characters.
  - `DEFAULT_CHUNK_OVERLAP = 150` characters.
- **Page Boundary Preservation:**
  - Every text chunk is processed page by page and preserves exact 1-indexed source `page_number`.
  - Text from different physical pages is never combined into a single chunk.
- **Empty Page Rule:**
  - If a page has empty text (`ParsedPage.text.strip() == ""`) and no tables, **0 text chunks** are created for that page, preventing useless empty vector records while maintaining parser page boundary tracking.

---

## 4. Table Chunking & Semantic Metadata

For each PDF `ExtractedTable`, a dedicated `chunk_type = "table"` chunk is generated using the deterministic Markdown representation (`table.markdown`).

### Metadata Fields Preserved:
```json
{
  "source_type": "table",
  "table_id": "tbl_1_1",
  "page_number": 1,
  "filename": "apple_10k_2025.pdf",
  "title": "Consolidated Statements of Operations",
  "statement_type": "income_statement",
  "confidence": 1.0,
  "period_type": "annual",
  "fiscal_periods": ["2025", "2024"],
  "currency": "USD",
  "units": "millions",
  "key_metrics": ["revenue", "gross_profit", "net_income"],
  "column_count": 3,
  "row_count": 4,
  "has_year_columns": true,
  "has_quarter_columns": false
}
```

---

## 5. Non-PDF Format Strategies

- **Plain Text (TXT):**
  - Text parsed via `TextParserService` $\rightarrow$ single logical page (page 1) $\rightarrow$ recursive text splitting.
- **CSV Documents:**
  - CSV parsed via `CSVParserService` $\rightarrow$ structured table chunking.
  - For small CSVs, creates 1 structured table chunk (`chunk_type = "table"`, `format = "csv"`).
  - For large CSVs, splits rows deterministically while repeating the header line on each split chunk.

---

## 6. Deterministic Ordering

Chunks are ordered deterministically:
1. Primary order: `page_number`
2. Intra-page order: Page text chunks followed by page table chunks
3. Sequential 0-indexed `chunk_index` assigned monotonically across the document.

---

## 7. Two-Phase Transaction Safety & Idempotency

Implemented in [`backend/app/tasks/definitions.py`](file:///d:/Portfolio%20soft%20projects/finsight/finsight/backend/app/tasks/definitions.py):

- **Success Sequence (Single Atomic Transaction):**
  1. `BEGIN DB TRANSACTION`
  2. `DELETE FROM chunks WHERE document_id = doc_uuid;` (prevents duplicate chunks on reprocessing)
  3. `INSERT INTO chunks (...) VALUES (...);` (all `embedding` values set to `NULL`)
  4. `UPDATE documents SET total_chunks = len(chunks), status = 'parsed', processing_error = NULL;`
  5. `COMMIT;`
- **Failure Sequence (Two-Phase Isolation):**
  1. Error during processing triggers `ROLLBACK;` (zero partial chunk records remain)
  2. A **NEW** isolated transaction is initiated:
  3. `UPDATE documents SET status = 'failed', processing_error = error;`
  4. `COMMIT;`

---

## 8. Database Verification & Deferred Embeddings

- In Sprint 5.1, `Chunk.embedding` remains strictly `NULL` (`Vector(1536)`).
- Verified via SQL:
  ```sql
  SELECT chunk_type, count(*), count(embedding) FROM chunks GROUP BY chunk_type;
  ```
  Returns `count(embedding) == 0` across all text and table chunks.

---

## 9. Known Limitations

- **Text / Table Overlap:** Because PDF text extractors (pypdf) extract all characters on a page including table numbers, page text chunks may contain duplicate numbers that also appear in table Markdown chunks. Table-region geometric exclusion is intentionally deferred to avoid discarding critical financial notes.
