# FinSight Phase 11.2 API Client & Backend Type Integration

## 1. FastAPI Source of Truth
The FastAPI backend (`http://localhost:8085` or `http://localhost:8000`) serves as the strict, single source of truth for all data models, vector retrieval endpoints, multi-turn conversational agents, and asynchronous report generation tasks. The frontend never duplicates or invents contracts.

---

## 2. API Inventory

| Domain | HTTP Method | Endpoint | Request Payload / Params | Response Schema | Sync / Async |
|---|---|---|---|---|---|
| **Health** | `GET` | `/health` | None | `HealthResponse` (`status`, `app`, `version`) | Synchronous |
| **Documents** | `GET` | `/api/v1/documents/` | None | `DocumentListResponse` (`total`, `documents`) | Synchronous |
| **Documents** | `GET` | `/api/v1/documents/{id}` | Path: `id` (UUID) | `DocumentResponse` | Synchronous |
| **Documents** | `POST` | `/api/v1/documents/upload` | Multipart FormData (`file`, `title?`, `description?`, `source?`) | `DocumentUploadResponse` (`message`, `document`) | Async Ingestion Job Enqueued |
| **Documents** | `DELETE` | `/api/v1/documents/{id}` | Path: `id` (UUID) | `204 No Content` | Synchronous Cascade |
| **Search** | `POST` | `/api/v1/search` | `SearchRequest` (`query`, `top_k`, `min_similarity`, `document_id?`, `document_ids?`) | `SearchResponse` (`query`, `total_results`, `results`) | Synchronous Vector Retrieval |
| **RAG** | `POST` | `/api/v1/rag/query` | `RAGRequest` (`query`, `top_k`, `min_similarity`, `document_id?`, `document_ids?`) | `RAGResponseSchema` (`query`, `answer`, `citations`, `retrieved_chunks`, `grounded`) | Synchronous Grounded Generation |
| **Conversations** | `POST` | `/api/v1/conversations` | `CreateSessionRequest` (`title?`) | `ConversationSessionResponse` (`id`, `title`, `message_count`, `created_at`, `updated_at`) | Synchronous |
| **Conversations** | `GET` | `/api/v1/conversations/{id}` | Path: `id` (UUID) | `ConversationSessionResponse` | Synchronous |
| **Conversations** | `DELETE` | `/api/v1/conversations/{id}` | Path: `id` (UUID) | `DeleteSessionResponse` (`message`, `session_id`) | Synchronous Cascade |
| **Conversations** | `GET` | `/api/v1/conversations/{id}/messages` | Path: `id` (UUID), Query: `limit=50` | `ConversationMessageResponse[]` | Synchronous Chronological |
| **Conversations** | `POST` | `/api/v1/conversations/{id}/query` | Path: `id` (UUID), `ConversationQueryRequest` (`query`, `top_k`, `min_similarity`, `document_ids?`) | `ConversationQueryResponse` (`session_id`, `query`, `resolved_query`, `answer`, `citations`, `retrieved_chunks`, `grounded`) | Synchronous Multi-Turn Agent |
| **Reports** | `POST` | `/api/v1/reports` | `CreateReportRequest` (`query`, `title?`, `document_ids?`, `report_type?`) | `ReportResponse` (`id`, `status: "pending"`, ...) | `202 Accepted` (Async Worker) |
| **Reports** | `GET` | `/api/v1/reports/{id}` | Path: `id` (UUID) | `ReportResponse` (`id`, `status`, `executive_summary`, `findings`, `content`, `citations`, ...) | Synchronous Status/Payload Check |
| **Reports** | `GET` | `/api/v1/reports` | Query: `status?`, `limit=50`, `offset=0` | `ReportListResponse` (`total`, `reports`) | Synchronous Bounded List |
| **Reports** | `DELETE` | `/api/v1/reports/{id}` | Path: `id` (UUID) | `204 No Content` | Synchronous |

---

## 3. Type Strategy & OpenAPI Usage
- The backend OpenAPI schema at `/openapi.json` was extracted and inspected directly from the running FastAPI application.
- All TypeScript contracts in [frontend/types/api.ts](file:///d:/Portfolio%20soft%20projects/finsight/finsight/frontend/types/api.ts) strictly mirror the Pydantic schemas:
  - Document statuses: `"pending" | "processing" | "parsed" | "indexed" | "failed"`
  - Report statuses: `"pending" | "processing" | "completed" | "failed"`
  - Financial Finding contracts: `metric`, `period`, `value`, `unit`, `source_chunk_ids`, `calculation`
  - Citation contracts: `chunk_id`, `document_id`, `page_number`, `chunk_type`, `similarity`, `statement_type`, `fiscal_periods`

---

## 4. Centralized API Client Architecture
- Located at [frontend/lib/api/client.ts](file:///d:/Portfolio%20soft%20projects/finsight/finsight/frontend/lib/api/client.ts).
- Configurable base URL reading `NEXT_PUBLIC_API_URL`.
- Normalized `ApiError` class capturing HTTP status, backend error code (`VALIDATION_ERROR`, `NOT_FOUND`, `UNPROCESSABLE_ENTITY`, `EXTERNAL_SERVICE_ERROR`, `INTERNAL_SERVER_ERROR`), error message, and validation details.
- Clean FormData handling without overriding multipart boundaries.
- Cross-environment `AbortSignal` cancellation support.

---

## 5. Domain Services
Framework-independent TypeScript modules in `frontend/lib/api/`:
- `documents.ts`: `list`, `get`, `upload`, `delete`
- `search.ts`: `search`
- `rag.ts`: `query`
- `conversations.ts`: `createSession`, `getSession`, `deleteSession`, `getMessages`, `querySession`
- `reports.ts`: `create`, `get`, `list`, `delete`
- `health.ts`: `check`

---

## 6. TanStack Query Hooks & Query Key Conventions
Centralized query key factory in `frontend/lib/api/query-keys.ts` with dedicated domain hooks in `frontend/hooks/`:
- `use-documents.ts`:
  - `useDocuments()`: Lists documents with smart polling (2.5s) if any document is in `pending` or `processing`.
  - `useDocument(id)`: Fetches single document with polling until terminal status (`indexed` or `failed`).
  - `useUploadDocument()`, `useDeleteDocument()`: Mutations with deterministic cache invalidation.
- `use-search.ts`: `useSearch(params)`, `useSearchMutation()`.
- `use-rag.ts`: `useRagQuery()`.
- `use-conversations.ts`: `useConversationSession(id)`, `useConversationMessages(id)`, `useCreateSession()`, `useDeleteSession()`, `useConversationQuery(sessionId)`.
- `use-reports.ts`:
  - `useReports(params)`: Lists reports with 3s polling for active items.
  - `useReport(reportId)`: Fetches report details with 2s polling until `completed` or `failed`.
  - `useCreateReport()`, `useDeleteReport()`: Mutations with cache invalidation.

---

## 7. Testing & MSW Mock Architecture
- **MSW Node Server**: `frontend/tests/mocks/` intercepting all backend REST routes with faithful schemas.
- **Unit & Integration Suite**: 39/39 passing tests across API client, domain services, and TanStack Query hooks.
- **Live Integration Check**: Verified live communication with Docker container backend (`/health` and `/api/v1/documents/`).

---

## 8. Security Confirmation
- No Gemini API keys, PostgreSQL credentials, or Redis credentials are exposed or imported into frontend bundles.
- Only browser-safe variables (`NEXT_PUBLIC_API_URL`) are read by the client.
