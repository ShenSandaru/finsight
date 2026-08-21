# FinSight Grounded RAG Context Assembly & Answer Generation (Sprint 7.1)

## Overview

Sprint 7.1 establishes the grounded financial question-answering (RAG) layer for FinSight on top of the verified Sprints 1–6.2 ingestion and vector retrieval pipeline.

The architecture answers natural language financial questions strictly from retrieved document chunks, formats source citations directly from database chunk metadata, validates citations in the LLM response, and gracefully short-circuits when evidence is insufficient without making unnecessary external LLM calls.

---

## 1. RAG Architecture & Flow

```text
User Financial Question (POST /api/v1/rag/query)
        ↓
RAG API Router (`app/api/routes/rag.py`)
        ↓
RAGService (`app/services/rag_service.py`)
        ↓
RetrievalService.search() (PostgreSQL pgvector cosine distance search)
        ↓
Top-K RetrievalResult Chunks
        ↓
Relevance Threshold Check (chunks >= min_similarity?)
   ├── NO (0 chunks or all < min_similarity) ──> Return standard insufficient evidence response (grounded: false)
   └── YES (Valid evidence retrieved)
            ↓
Context Assembly (`build_context`)
  -> Ranked blocks formatted with [SOURCE 1], [SOURCE 2], etc.
  -> Strict character budget (RAG_MAX_CONTEXT_CHARS = 18000)
  -> Zero mid-chunk splitting
  -> Extracts structured list[SourceCitation]
            ↓
Grounded System Instruction + Prompt
  -> Strict grounding: No outside knowledge, no invented figures
  -> Unit & currency preservation
  -> Period identification & point-in-time vs period distinction
            ↓
GenerationService (`app/services/generation_service.py`)
  -> Google Gemini 2.0 Flash (`gemini-2.0-flash`)
  -> Asynchronous `client.aio.models.generate_content(...)`
  -> Temperature: 0.1, Max Output Tokens: 1200
  -> Bounded exponential backoff retry on transient API errors
            ↓
Citation Validation (`validate_and_clean_citations`)
  -> Strips any out-of-bounds [SOURCE N] markers
            ↓
Grounded RAG Response (`RAGResponse` / `RAGResponseSchema`)
```

---

## 2. Context Assembly & Source Identifiers

### Budget & Preservation Rules
- **Maximum Context Size:** `RAG_MAX_CONTEXT_CHARS = 18000`
- **Ranking Preservation:** Chunks are placed in the prompt in the exact descending order returned by `RetrievalService`.
- **Atomic Inclusion:** If adding a chunk would exceed `18,000` characters, context assembly stops cleanly. No chunk is ever truncated or split mid-sentence.
- **Source Numbering:** Each block begins with `[SOURCE 1]`, `[SOURCE 2]`, ... matching 1-to-1 with the structured `citations` list in the response.

### Example Context Format
```text
[SOURCE 1]
Document ID: 95021db6-0db2-41ee-b168-a76ec56102f5
Chunk ID: f8d61af9-4151-424a-beb4-89db07feae70
Page: 1
Chunk Type: table
Similarity: 0.8346
Statement Type: income_statement
Fiscal Periods: 2025, 2024
Currency: USD
Units: millions

Content:
| Financial Metric | 2025 | 2024 |
| Total Revenue | $1,000 | $900 |
| Gross Profit | $400 | $360 |
| Net Income | $150 | $130 |
```

---

## 3. Grounding & System Instructions

### System Instruction (`GROUNDING_SYSTEM_INSTRUCTION`)
The generation service passes the following strict instructions to Gemini:
```text
You are a financial document question-answering assistant.
Use ONLY the supplied FinSight document context.

Rules:
1. Never use outside knowledge.
2. Never invent financial values, dates, periods, currencies, or units.
3. Preserve exact financial units and currency (e.g., millions, billions, $, EUR).
4. Distinguish annual, quarterly, YTD, and point-in-time values.
5. When comparing periods, identify the periods explicitly.
6. Use only evidence present in the supplied context.
7. Cite supporting evidence using [SOURCE N] (e.g., [SOURCE 1]).
8. Never fabricate a [SOURCE N] identifier that is not in the provided evidence.
9. If evidence is insufficient, clearly state that the indexed documents do not provide enough information.
10. Do not claim information unsupported by the supplied evidence.
11. Keep answers concise, factual, and professional.
```

---

## 4. Insufficient Evidence Short-Circuit

If `RetrievalService` returns zero results above `min_similarity` (default `0.30`):
1. **Zero LLM Calls:** Gemini is not called, conserving API quota and preventing hallucinations.
2. **Standardized Response:**
   ```json
   {
     "query": "What was the company's dividend yield?",
     "answer": "I could not find enough relevant information in the indexed documents to answer this question.",
     "citations": [],
     "retrieved_chunks": 0,
     "grounded": false
   }
   ```

---

## 5. Citation Architecture & Validation

- **Ground Truth Citations:** Citation metadata (`chunk_id`, `document_id`, `page_number`, `chunk_type`, `statement_type`, `fiscal_periods`, `similarity`) is constructed strictly from database `RetrievalResult` objects.
- **Citation Sanitization:** If the model outputs an unsupported citation marker (such as `[SOURCE 99]` when only 2 sources were provided), `validate_and_clean_citations` automatically strips the out-of-bounds marker before returning the answer.

---

## 6. REST API Endpoint

### `POST /api/v1/rag/query`

**Request:**
```json
{
  "query": "What was the total revenue in 2025?",
  "top_k": 5,
  "min_similarity": 0.30,
  "document_id": "95021db6-0db2-41ee-b168-a76ec56102f5"
}
```

**Response (HTTP 200):**
```json
{
  "query": "What was the total revenue in 2025?",
  "answer": "Total revenue for 2025 was $1,000 million, an increase from $900 million in 2024. [SOURCE 1]",
  "citations": [
    {
      "chunk_id": "f8d61af9-4151-424a-beb4-89db07feae70",
      "document_id": "95021db6-0db2-41ee-b168-a76ec56102f5",
      "page_number": 1,
      "chunk_type": "table",
      "similarity": 0.8346,
      "statement_type": "income_statement",
      "fiscal_periods": ["2025", "2024"]
    }
  ],
  "retrieved_chunks": 1,
  "grounded": true
}
```

---

## 7. Deferred Architectural Scope

To maintain disciplined sprint boundaries, the following were intentionally deferred:
- **Conversation Memory:** No multi-turn chat history or session state (Sprint 7.2+).
- **Query Rewriting / Expansion:** Raw user query is passed directly to the vector retrieval index.
- **Cross-Encoder Reranking:** pgvector cosine similarity ranking is used directly.
- **Multi-Agent Orchestration:** Specialized agents (planners, verifiers, synthesizers) belong to Phase 9.
