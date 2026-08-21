# FinSight Conversational Memory & Multi-Turn RAG Session Management (Sprint 8.2)

## Overview

Sprint 8.2 extends FinSight's grounded RAG capabilities from isolated single-turn queries into **stateful, session-based multi-turn research conversations**.

The architecture preserves conversation history across turns, resolves follow-up queries using prior contextual entities and metrics, guarantees strict session isolation in PostgreSQL, and enforces that previous conversation turns never become fake citation evidence.

---

## 1. Multi-Turn RAG Architecture & Flow

```text
User Follow-Up ("What about 2024?")
        ↓
POST /api/v1/conversations/{session_id}/query
        ↓
ConversationService (`app/services/conversation_service.py`)
        ↓
1. Validate Session & Query Length
2. Persist User Message to PostgreSQL
3. Load Recent Messages (chronological, max 10)
        ↓
QueryContextService (`app/services/query_context_service.py`)
  -> Detects follow-up pattern
  -> Combines relevant context: "Apple revenue 2024"
  -> Preserves original user wording for answer generator
        ↓
RAGService (`app/services/rag_service.py`)
  -> RetrievalService.search() (pgvector HNSW cosine search)
  -> Context Assembly with [SOURCE 1], [SOURCE 2] (18k char limit)
  -> Gemini 2.0 Flash Generation
  -> Citation Validation against retrieved chunks
        ↓
4. Persist Assistant Answer to PostgreSQL
        ↓
Grounded Multi-Turn Response (`ConversationQueryResponse`)
```

---

## 2. Core Architectural Rules & Principles

### A. Conversation History Is NOT Financial Evidence
- Prior assistant or user messages are contextual only.
- Citations (`[SOURCE 1]`, `[SOURCE 2]`) and structured `CitationResponse` objects are generated exclusively from in-database `RetrievalResult` chunk records.
- Previous messages are never injected as citation sources.

### B. Session Isolation
- Every database query for messages is strictly filtered by `session_id`.
- Messages from Session A are completely invisible to Session B.

### C. Failure Resilience
- If the RAG or LLM generation step encounters an error (e.g. timeout or API rate limit), the user's initial message remains persisted in the database, allowing retry without data loss.

---

## 3. Database Schema & Models

### `conversation_sessions` Table
| Column | Type | Constraints / Details |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary Key (`default=uuid.uuid4`) |
| `title` | `VARCHAR(255)` | Optional session title |
| `created_at` | `TIMESTAMP` | Session creation timestamp |
| `updated_at` | `TIMESTAMP` | Auto-updated on new messages |

### `conversation_messages` Table
| Column | Type | Constraints / Details |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary Key (`default=uuid.uuid4`) |
| `session_id` | `UUID` | Foreign Key (`conversation_sessions.id`, `ON DELETE CASCADE`), Indexed |
| `role` | `VARCHAR(20)` | `'user'` or `'assistant'` |
| `content` | `TEXT` | Raw message content |
| `created_at` | `TIMESTAMP` | Message timestamp, Indexed (`ix_conversation_messages_session_created`) |

---

## 4. REST API Endpoints

### 1. Create Session
`POST /api/v1/conversations`
- **Request:** `{"title": "Apple 10-K Research"}`
- **Response (201 Created):**
  ```json
  {
    "id": "9f316e32-87b6-41b3-aa15-4777d72f6202",
    "title": "Apple 10-K Research",
    "created_at": "2026-08-21T19:50:00.000000",
    "updated_at": "2026-08-21T19:50:00.000000",
    "message_count": 0
  }
  ```

### 2. Get Session Metadata
`GET /api/v1/conversations/{session_id}`

### 3. Get Session Message History
`GET /api/v1/conversations/{session_id}/messages?limit=50`
- Returns messages in chronological order.

### 4. Delete Session
`DELETE /api/v1/conversations/{session_id}`
- Deletes session and cascades deletion of all associated messages.

### 5. Multi-Turn Query
`POST /api/v1/conversations/{session_id}/query`
- **Request:**
  ```json
  {
    "query": "What about 2024?",
    "top_k": 5,
    "min_similarity": 0.30
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "session_id": "9f316e32-87b6-41b3-aa15-4777d72f6202",
    "query": "What about 2024?",
    "resolved_query": "What was the total revenue in 2024",
    "answer": "In 2024, total revenue was $900 million. [SOURCE 1]",
    "citations": [
      {
        "chunk_id": "f8d61af9-4151-424a-beb4-89db07feae70",
        "document_id": "1e8a0da8-0536-4516-9ff9-5cb0f778f422",
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

## 5. Explicitly Deferred Scope
The following items remain reserved for subsequent phases:
- **Vectorized Conversation Memory:** Embedding conversation turns into pgvector.
- **LLM-Based Multi-Turn Summarization:** Compacting long chat histories using Gemini calls.
- **Cross-Encoder Reranking & BM25 Hybrid Retrieval:** (Phase 9+).
- **Multi-Agent Research Teams:** Specialized planner, verifier, and analyst agents (Phase 9+).
