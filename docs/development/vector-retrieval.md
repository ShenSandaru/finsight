# FinSight Vector Similarity Search & Retrieval Foundation (Sprint 6.2)

## Overview

Sprint 6.2 implements the semantic vector similarity retrieval layer for FinSight on top of the 1536-dimensional Gemini embeddings persisted in PostgreSQL. It enables exact, deterministic vector similarity searches over chunk embeddings while strictly keeping RAG answer generation, query expansion, and LLM text completion outside the feature boundary.

---

## 1. Query Embedding Generation

### Task Semantics: `RETRIEVAL_QUERY`
In Gemini's embedding specification, document text and search queries require asymmetric embedding task types:
- Document chunks stored in PostgreSQL: `task_type="RETRIEVAL_DOCUMENT"`
- User search queries: `task_type="RETRIEVAL_QUERY"`

### Method: `EmbeddingService.embed_query`
- **Location:** `backend/app/services/embedding_service.py`
- **Input Validation:** Rejects empty or whitespace-only queries immediately before making network or API calls.
- **Model & Dimension:** Uses `gemini-embedding-2` configured for `output_dimensionality=1536`.
- **Dimension Validation:** Validates that the returned float list contains exactly 1536 elements before downstream processing.
- **Resilience:** Reuses existing bounded exponential backoff retries on transient network errors (HTTP 429, 500, 503, timeouts).

---

## 2. In-Database Vector Similarity Search

### PostgreSQL & pgvector Engine
All similarity calculations, cosine distance operations, score filtering, and limit operations execute directly inside PostgreSQL. No vectors are pulled into application memory for Python-side sorting.

- **pgvector Extension Version:** `0.8.6` (running in PostgreSQL 16)
- **Python SQLAlchemy pgvector Version:** `0.2.4` / SQLAlchemy `2.0.23`
- **Operator:** `<=>` (Cosine Distance)
- **Similarity Formula:**
  $$\text{similarity} = 1.0 - (\text{chunk.embedding} \Leftrightarrow \text{query\_vector})$$

### SQL Query Architecture
```sql
SELECT
    chunk.id,
    chunk.document_id,
    chunk.content,
    chunk.chunk_type,
    chunk.chunk_index,
    chunk.page_number,
    chunk.metadata,
    1.0 - (chunk.embedding <=> :query_vector) AS similarity
FROM chunks AS chunk
JOIN documents AS document
    ON document.id = chunk.document_id
WHERE chunk.embedding IS NOT NULL
  AND document.status = 'indexed'
  AND (:document_id IS NULL OR chunk.document_id = :document_id)
  AND (1.0 - (chunk.embedding <=> :query_vector) >= :min_similarity)
ORDER BY
    similarity DESC,
    chunk.chunk_index ASC,
    chunk.id ASC
LIMIT :top_k;
```

---

## 3. Retrieval Result Contract & Service

### Data Contract (`RetrievalResult`)
```python
@dataclass
class RetrievalResult:
    chunk_id: UUID
    document_id: UUID
    content: str
    chunk_type: str
    chunk_index: int
    page_number: int | None
    similarity: float
    metadata: dict[str, Any]
```

### Retrieval Service (`RetrievalService`)
- **Location:** `backend/app/services/retrieval_service.py`
- **Filtering Rules:**
  - Excludes chunks with `embedding IS NULL`.
  - Excludes chunks from non-`indexed` documents (e.g. `pending`, `processing`, `parsed`, `failed`).
  - Supports optional document scoping via `document_id`.
  - Supports configurable `min_similarity` (default: `0.0`, range: `0.0` to `1.0`).
  - Supports bounded `top_k` (default: `5`, max: `20`).
- **Deterministic Ordering:** Ties in similarity are strictly resolved by `chunk_index ASC` followed by `chunk.id ASC`.
- **Preserved Metadata:** Table semantics (`statement_type`, `fiscal_periods`, `currency`, `confidence`), page numbers, and chunk types are fully preserved.

---

## 4. API Endpoints

### Endpoint: `POST /api/v1/search`
- **Request Body (`SearchRequest`):**
  ```json
  {
    "query": "What was the company's annual revenue in 2025?",
    "top_k": 5,
    "min_similarity": 0.0,
    "document_id": null
  }
  ```
- **Response Body (`SearchResponse`):**
  ```json
  {
    "query": "What was the company's annual revenue in 2025?",
    "total_results": 2,
    "results": [
      {
        "chunk_id": "c1a2b3c4-...",
        "document_id": "d1a2b3c4-...",
        "content": "| Metric | 2025 |\n| Total Revenue | $1,000 |",
        "chunk_type": "table",
        "chunk_index": 0,
        "page_number": 1,
        "similarity": 0.8542,
        "metadata": {
          "statement_type": "income_statement",
          "fiscal_periods": ["2025"]
        }
      }
    ]
  }
  ```

---

## 5. Architectural Boundaries & Deferred Scope

1. **Exact Search Baseline:** No Approximate Nearest Neighbor (ANN) indexes (such as HNSW or IVFFlat) were created in this sprint. Exact cosine similarity provides the ground truth benchmark for retrieval correctness. Performance indexing will be introduced in a dedicated performance optimization sprint.
2. **No RAG / Generation:** No LLM answer generation, context assembly, conversational memory, or citation synthesis is performed at this stage. Sprint 6.2 strictly terminates after returning ranked retrieval results.
