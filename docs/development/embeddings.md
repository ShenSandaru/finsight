# Gemini Embedding Pipeline & pgvector Persistence

## 1. Overview
The FinSight Embedding Pipeline (Sprint 6.1) implements automated 1536-dimensional vector generation for document chunks using Google's modern `google-genai` SDK and the `gemini-embedding-2` model. The pipeline seamlessly enriches parsed text and financial table chunks with vector representations and atomically persists them into PostgreSQL using `pgvector`.

```
Document Upload (PDF/TXT/CSV)
       ↓
Parsing & Table Extraction (Sprint 3 & 4)
       ↓
Table-Aware Chunking & Semantic Metadata (Sprint 5.1)
       ↓
Chunk Persistence (status = "parsed", embedding = NULL)
       ↓
[SPRINT 6.1 PIPELINE]
1. Read document chunks (closed immediately)
2. Generate embeddings via EmbeddingService (batch size = 50, RETRIEVAL_DOCUMENT task type)
3. Validate vector dimensions (strictly 1536 floats)
4. Atomic DB Transaction (UPDATE Chunk.embedding, Document.status = "indexed")
       ↓
Document Ready for Future Semantic & Vector Retrieval (Phase 7+)
```

---

## 2. Model & SDK Architecture

- **Library:** Official `google-genai` SDK (`google-genai==0.8.0`).
- **Model:** `gemini-embedding-2`.
- **Dimensionality:** Exactly 1536 floats (`output_dimensionality = 1536`).
- **Task Type:** `RETRIEVAL_DOCUMENT` (specified via typed `types.EmbedContentConfig`).
- **Client Lifecycle:** Instantiated per service lifecycle with async client support (`client.aio`) and explicit resource cleanup via `close()`.

---

## 3. Resilience, Batching & Transaction Rules

### Deterministic Batching
Chunks are processed in sequential, deterministic batches of 50 (`EMBEDDING_BATCH_SIZE = 50`). Input-to-output ordering is strictly preserved so that chunk indices and vector arrays map 1-to-1:
```
input[0] -> vector[0]
input[1] -> vector[1]
...
```

### Bounded Exponential Backoff Retry Policy
Transient network and API errors are caught and retried with exponential backoff:
- Transient errors retried: HTTP 429 (Rate Limit), HTTP 500/502/503/504 (Server Errors, Unavailable), and `asyncio.TimeoutError`.
- Max retries: Bounded by `EMBEDDING_MAX_RETRIES = 3`.
- Backoff intervals: $0.5\text{s} \times 2^{\text{attempt}-1}$.
- Non-transient errors (missing API key, dimension mismatch, empty text) fail immediately without wasteful retries.

### Strict Dimension Validation
Every vector returned by Gemini is checked:
```python
if len(vec) != 1536:
    raise ProcessingError("Gemini returned invalid embedding dimension")
```
No vector is ever truncated or padded.

### Transaction Isolation (Rule A & B)
- **Rule A (Zero Open Transactions During API Calls):** Database transactions are never held open while waiting for external Gemini API calls. Chunks are queried first, embeddings are generated and validated, and only then is a dedicated atomic persistence transaction opened.
- **Rule B (Whole-Document Atomicity):** If any chunk embedding fails or dimension validation fails, zero vectors are committed. An isolated recovery transaction marks `Document.status = "failed"` with a sanitized `processing_error`.

### Idempotency & Zero-Chunk Safety
- If a document is already in `indexed` status and all chunks have non-null embeddings, API calls are skipped.
- If `total_chunks == 0`, the task transitions the document to `status = "failed"` with `processing_error = "No chunks available for embedding"`.

---

## 4. Testing & Fake Provider Architecture

For deterministic, completely offline automated tests, `FakeGenAIClient` generates reproducible 1536-dimensional unit-norm vectors using SHA-256 seed hashing of input chunk content.

- **Unit & Integration Suite:** 23 tests in `test_embedding_service.py` verifying batching, ordering, dimension rejection, retry on rate limits, connection errors, timeouts, missing credentials, database persistence, idempotency, and rollback.
- **Regression Suite:** 92 total backend tests passed with 0 failures.
- **E2E Pipeline:** `e2e_test.py` validates end-to-end multi-page PDFs, TXTs, and financial statements transitioning through `pending` $\rightarrow$ `processing` $\rightarrow$ `parsed` $\rightarrow$ `indexed` with non-null 1536-dimensional vectors in PostgreSQL.

---

## 5. Security & Secret Handling

- `GEMINI_API_KEY` is loaded exclusively from environment configuration.
- The API key is never logged, printed, stored in database fields, or exposed in `processing_error` diagnostics.
- Placeholder template provided in `.env.example`.

---

## 6. Deferred Features (Future Sprints)
The following are intentionally deferred and **NOT** implemented in Sprint 6.1:
- Vector similarity search (cosine distance queries `<=>`)
- HNSW or IVFFlat index creation
- Hybrid retrieval (BM25 + vector)
- `RETRIEVAL_QUERY` task type
- RAG answer generation & multi-agent orchestration
