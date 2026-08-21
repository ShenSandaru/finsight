# FinSight — Master Implementation Plan & Roadmap 🚀

This document defines the comprehensive, grounded implementation roadmap for **FinSight**, an AI-powered financial intelligence & investment research copilot.

---

## 1. Actual Current State Assessment

This assessment is strictly grounded on the current repository codebase (`finsight/`), models, services, routes, Docker configuration, and Git history.

### ✅ Completed & Verified in Code
* **Container & Infrastructure Orchestration:**
  * `docker-compose.yml` with PostgreSQL 16 (`pgvector/pgvector:pg16`), Redis 7 Alpine, and FastAPI backend service.
  * Database initialization script (`scripts/init.sql`) enabling PostgreSQL vector extension (`CREATE EXTENSION IF NOT EXISTS vector;`).
* **Core Application Configuration & Database Layer:**
  * Async SQLAlchemy 2.0 engine (`create_async_engine`) and session maker with asyncpg (`app/core/database.py`).
  * Centralized Pydantic settings management in `app/core/config.py` loading database URLs, Redis URL, file upload limits (50MB), and allowed extensions (`pdf`, `txt`, `csv`).
  * Database initialization on startup via FastAPI `lifespan` handler (`app/main.py`).
* **Database Models (SQLAlchemy 2.0 ORM):**
  * `Document` (`app/models/document.py`): UUID primary key, file metadata (`filename`, `file_type`, `file_size`, `title`, `description`, `source`), status tracking (`status` defaulting to `pending`), page/chunk counts, UTC timestamps, and cascading one-to-many relationship with `Chunk`.
  * `Chunk` (`app/models/chunk.py`): UUID primary key, foreign key referencing `documents.id`, `content` (Text), `embedding` (`Vector(1536)`), `chunk_type` (`text`, `table`, etc.), `chunk_index`, `page_number`, `metadata_` (JSONB), and relationship back to `Document`.
  * `Report` (`app/models/report.py`): UUID primary key, `query`, `response`, `sources` (JSONB), `report_type`, `status`, and timestamps.
* **Document Ingestion & Storage API:**
  * `DocumentService` (`app/services/document_service.py`): File validation (extension check, max file size), async disk storage (`aiofiles`) in `/app/storage/documents/` with UUID-prefixed filenames, DB record insertion, retrieval (`get_document`, `get_all_documents`), and deletion with local file cleanup.
  * API endpoints (`app/api/routes/documents.py`):
    * `POST /api/v1/documents/upload`
    * `GET /api/v1/documents/`
    * `GET /api/v1/documents/{document_id}`
    * `DELETE /api/v1/documents/{document_id}`
  * Pydantic schemas (`app/schemas/document.py`): `DocumentResponse`, `DocumentUploadResponse`, and `DocumentListResponse`.

---

### 🔄 Partially Implemented / Incomplete
* **Async Background Task Queue:** Redis container is running and healthy, and settings specify `REDIS_URL`, but no Celery / ARQ / Redis queue or background worker logic is wired to `DocumentService`. When a file is uploaded, it is saved with `status = "pending"` but no background job is triggered.
* **PDF / Document Parsing:** Active Git branch is `feat/pdf-parsing`, but no parser module exists in `app/services/` yet. `requirements.txt` contains basic web and DB libraries (`fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `pgvector`, `redis`, `httpx`, `aiofiles`, `python-multipart`), but no PDF parsing libraries (`pypdf`, `pdfplumber`, `unstructured`, etc.) or AI libraries (`openai`, `langchain`, `langgraph`).

---

### ❌ Not Implemented (Documented/Planned Only)
* **Table-aware parsing & structured financial data extraction.**
* **Chunking service** (page-aware, section-aware, and financial table preserving).
* **Embedding generation** (OpenAI / HuggingFace embedding integration).
* **Vector similarity search & pgvector indexing** (HNSW / IVFFlat indexing and query functions).
* **RAG query pipeline** (context assembly, citation/evidence tracing, prompt construction).
* **Multi-Agent Orchestrator** (Retriever, Analyzer, Financial Verification/Critic, and Writer agents).
* **Query & Report API routes** (`/api/v1/query`, `/api/v1/reports`).
* **Frontend UI** (`frontend/` directory is currently empty).
* **Automated Unit & Integration Test Suite** (No `tests/` directory present).
* **Database Migrations** (Alembic configuration is absent; DB schema is created via `Base.metadata.create_all`).

---

### ⚠️ Technical Debt & Pre-requisite Fixes
1. **Missing Database Migration Tool (Alembic):** Relying on `Base.metadata.create_all` in `lifespan` prevents smooth schema evolution once vector indexes and additional columns are added.
2. **Missing Async Processing Pipeline:** Document parsing, chunking, and embedding generation are compute- and I/O-intensive. They must not run blocking inside HTTP upload requests.
3. **Repository Directory Duplication:** The repository root contains an outer wrapper with a nested `finsight/` folder containing the actual backend, docker files, and configs.

---

## 2. Intended System Architecture

```mermaid
flowchart TD
    subgraph ClientLayer ["Client Layer"]
        UI["React / Next.js Web UI"]
    end

    subgraph APILayer ["FastAPI Application (app/api/)"]
        DocRoute["/api/v1/documents (Upload / Status)"]
        QueryRoute["/api/v1/query (Interactive Chat / RAG)"]
        ReportRoute["/api/v1/reports (In-depth Research)"]
        HealthRoute["/health"]
    end

    subgraph ServiceLayer ["Service Layer (app/services/)"]
        DocSvc["DocumentService"]
        ParserSvc["PDF / Document Parser"]
        TableSvc["Financial Table Extractor"]
        ChunkerSvc["Table-Aware Chunker"]
        EmbedSvc["Embedding Service"]
        RetrieverSvc["Hybrid / Vector Retriever"]
    end

    subgraph AgentLayer ["Multi-Agent Orchestrator (app/agents/)"]
        Graph["LangGraph Workflow"]
        RetrieverAgent["Retriever Agent"]
        AnalyzerAgent["Financial Analyzer Agent"]
        CriticAgent["Verification & Citation Critic"]
        WriterAgent["Report Synthesis Agent"]
    end

    subgraph StorageLayer ["Data & Queue Layer"]
        Storage["Local Disk / Object Storage (/app/storage)"]
        Redis["Redis (Task Queue / Cache)"]
        Postgres[("PostgreSQL 16 + pgvector")]
    end

    UI -->|HTTP / WebSocket| APILayer
    DocRoute --> DocSvc
    DocSvc --> Storage
    DocSvc -->|Enqueue Task| Redis
    Redis -->|Background Worker| ParserSvc
    ParserSvc --> TableSvc
    TableSvc --> ChunkerSvc
    ChunkerSvc --> EmbedSvc
    EmbedSvc -->|Store Chunks & Embeddings| Postgres

    QueryRoute --> Graph
    ReportRoute --> Graph
    Graph --> RetrieverAgent
    RetrieverAgent --> RetrieverSvc
    RetrieverSvc -->|Similarity Search (cosine)| Postgres
    Graph --> AnalyzerAgent
    Graph --> CriticAgent
    Graph --> WriterAgent
```

---

## 3. Implementation Roadmap (Phases 1 to 16)

---

### Phase 1 — Repository Baseline & Async Task Infrastructure
* **Goal:** Establish migration tooling (Alembic), configure background task worker with Redis, and standardize backend dependencies.
* **Why Needed:** Document parsing and embedding are long-running operations that will timeout or block HTTP requests. Alembic is essential for managing vector index creation and future schema changes.
* **Current Status:** Completed (Alembic baseline + ARQ Redis task worker + Standardized errors).
* **Tasks:**
  - [x] Add `alembic` to `backend/requirements.txt` and initialize migrations (`alembic init alembic`).
  - [x] Generate baseline migration representing existing `Document`, `Chunk`, and `Report` tables.
  - [x] Implement async background processing using Redis (`ARQ` worker container with Redis task state tracking).
  - [x] Create standardized service exception classes and uniform API error schemas.
* **Files Likely Affected:**
  - `backend/requirements.txt`
  - `backend/alembic.ini`
  - `backend/alembic/`
  - `backend/app/core/config.py`
  - `backend/app/core/tasks.py`
* **Acceptance Criteria:**
  - Alembic migrations run cleanly against PostgreSQL container.
  - An async task can be enqueued to Redis and execute out-of-band with status reporting.

---

### Phase 2 — Document Ingestion Hardening
* **Goal:** Harden the existing document upload flow with content validation, mime-type verification, and background worker triggering.
* **Why Needed:** Currently, uploads write to disk and DB but stay in `"pending"` status forever.
* **Current Status:** Completed (Magic-byte validation + ARQ worker trigger + Document.status transitions + processing_error).
* **Tasks:**
  - [x] Add magic-byte file header validation (protect against renamed malicious binaries).
  - [x] Trigger background processing pipeline immediately upon successful file upload.
  - [x] Update `Document.status` state machine (`pending` -> `processing` -> `failed`).
  - [x] Add processing error detail field to `Document` model for diagnostic visibility.
* **Files Likely Affected:**
  - `backend/app/models/document.py`
  - `backend/app/services/document_service.py`
  - `backend/app/api/routes/documents.py`
* **Acceptance Criteria:**
  - Uploading a valid PDF triggers background processing and returns `201 Created` with initial document status.

---

### Phase 3 — PDF & Document Parsing
* **Goal:** Implement robust text and page extraction from financial documents (10-K, 10-Q, earnings transcripts).
* **Why Needed:** RAG requires granular text extraction mapped accurately to page numbers for source citations.
* **Current Status:** Completed (Sprint 3.1 PDF parsing + Sprint 3.2 TXT/CSV parsing and conservative boilerplate filtering verified).
* **Tasks:**
  - [x] Add `pypdf==4.1.0` to `backend/requirements.txt`.
  - [x] Create `PDFParserService` (`app/services/pdf_parser.py`) supporting:
    - [x] Page-by-page text extraction and 1-indexed numbering.
    - [x] Page boundary tracking with empty/blank page preservation.
    - [x] Conservative, lightweight text normalization.
    - [x] Document metadata extraction (title, total pages, author/creator/creation date).
  - [x] Handle malformed, missing, and encrypted PDF exceptions gracefully with `document.status = "failed"` and `processing_error`.
  - [x] Wire `process_document` task in `app/tasks/definitions.py` with `Document.status` transition (`pending` -> `processing` -> `parsed`/`failed`).
  - [x] Support plain text (`.txt`) parsing (`TextParserService`) and CSV (`.csv`) parsing (`CSVParserService`) (Sprint 3.2).
  - [x] Conservative repeated boilerplate and header/footer detection (`PDFParserService.filter_repeated_boilerplate`) (Sprint 3.2).
* **Files Likely Affected:**
  - `backend/requirements.txt`
  - `backend/app/services/pdf_parser.py`
  - `backend/app/services/text_parser.py`
  - `backend/app/services/csv_parser.py`
  - `backend/app/tasks/definitions.py`
  - `backend/tests/`
  - `docs/development/pdf-parsing.md`
* **Acceptance Criteria:**
  - Parsed PDF produces a structured document representation (`ParsedDocument` with `ParsedPage`s): page numbers, raw text, and page metadata without dropping pages or crashing on standard corporate 10-K filings.
  - Parsed TXT and CSV produce structured `ParsedDocument`s representing 1 logical page with tabular structure preserved.

---

### Phase 4 — Financial Table Extraction & Semantics
* **Goal:** Extract and preserve structural layout of balance sheets, income statements, and cash flow tables, and enrich them with deterministic semantic classifications.
* **Why Needed:** Financial analysis relies heavily on tabular metrics. Standard text extractors scramble table rows and column headers, making numbers incomprehensible to LLMs.
* **Current Status:** Completed (Sprint 4.1 pdfplumber table extraction + Sprint 4.2 FinancialTableSemanticService statement classification, period extraction, and metric normalization verified).
* **Tasks:**
  - [x] Add `pdfplumber==0.11.0` to `backend/requirements.txt`.
  - [x] Implement table detection and extraction in `TableExtractorService` (`app/services/table_extractor.py`) using `pdfplumber`.
  - [x] Convert extracted tables into markdown format and structured JSON representation (preserving column headers, fiscal periods, currencies, and units).
  - [x] Generate deterministic Markdown and extract headers/titles for tables.
  - [x] Financial Statement Semantic Classification & Period Detection (`FinancialTableSemanticService` in `app/services/table_semantics.py`) (Sprint 4.2).
  - [ ] Table-aware chunking and tagging with `chunk_type = "table"` linked to page numbers (Phase 5).
* **Files Likely Affected:**
  - `backend/requirements.txt`
  - `backend/app/services/table_extractor.py`
  - `backend/app/services/table_semantics.py`
  - `backend/app/tasks/definitions.py`
  - `backend/tests/test_table_extractor.py`
  - `backend/tests/test_table_semantics.py`
  - `docs/development/table-extraction.md`
  - `docs/development/table-semantics.md`
* **Acceptance Criteria:**
  - Financial statements and tabular data in PDFs are extracted into structured `ExtractedTable` objects with aligned rows, columns, monetary units, currencies, Markdown serialization, and semantic classifications (`FinancialTableSemantics`) without creating database Chunk records.

---

### Phase 5 — Table-Aware Chunking Strategy
* **Goal:** Split extracted document text and tables into semantically coherent, citation-traceable chunks and persist them to PostgreSQL.
* **Why Needed:** LLM context windows and embedding models require chunks that do not cut sentences or table rows in half.
* **Current Status:** Completed (Sprint 5.1 TableAwareChunkerService, deterministic text & table chunking, JSONB semantic metadata, and transactional chunk persistence verified).
* **Tasks:**
  - [x] Create `TableAwareChunkerService` (`app/services/chunker.py`) and `ChunkData` contract (Sprint 5.1).
  - [x] Implement recursive text splitter for narrative sections (target size: 1200 characters, overlap: 150 characters) strictly preserving `page_number` (Sprint 5.1).
  - [x] Implement atomic table chunking: Keep PDF tables intact using Markdown formatting, enriched with statement semantics (`statement_type`, `period_type`, `fiscal_periods`, `currency`, `units`, `key_metrics`) (Sprint 5.1).
  - [x] Support plain text (TXT) and CSV structured chunking with repeated header rows for large files (Sprint 5.1).
  - [x] Two-phase transactional chunk persistence in worker pipeline (`app/tasks/definitions.py`) with atomic replacement / idempotency protection (Sprint 5.1).
  - [x] Save generated chunks to PostgreSQL with `chunk_type` (`text` vs `table`) and `embedding = NULL` (Sprint 5.1).
* **Files Likely Affected:**
  - `backend/app/core/config.py`
  - `backend/app/services/chunker.py`
  - `backend/app/tasks/definitions.py`
  - `backend/tests/test_chunker.py`
  - `backend/tests/e2e_test.py`
  - `docs/development/chunking.md`
* **Acceptance Criteria:**
  - Chunks retain complete semantic sentences and table Markdown representations; every chunk contains accurate `page_number`, sequential `chunk_index`, and `document_id`; `Document.total_chunks` matches actual `Chunk` row counts in PostgreSQL with `embedding = NULL`.

---

### Phase 6 — Embedding Pipeline & Vector Retrieval Foundation
* **Goal:** Generate vector embeddings for all document chunks, store them in PostgreSQL via `pgvector`, and execute exact vector similarity searches.
* **Why Needed:** Semantic search and RAG require vector representations and deterministic database similarity retrieval.
* **Current Status:** Completed (Sprint 6.1 Embedding persistence & Document `status = "indexed"` + Sprint 6.2 `RetrievalService`, `POST /api/v1/search`, and in-database pgvector cosine search verified).
* **Tasks:**
  - [x] Add `google-genai==0.8.0` to `backend/requirements.txt` (Sprint 6.1).
  - [x] Implement `EmbeddingService` (`app/services/embedding_service.py`) (Sprint 6.1 & 6.2):
    - [x] Gemini `gemini-embedding-2` model with `RETRIEVAL_DOCUMENT` task type and 1536 output dimensionality (Sprint 6.1).
    - [x] Query embedding generation with `RETRIEVAL_QUERY` task semantics via `EmbeddingService.embed_query` (Sprint 6.2).
    - [x] Deterministic batch embedding generation (batch size = 50) preserving 1-to-1 input-to-output ordering (Sprint 6.1).
    - [x] Bounded exponential backoff retry policy for transient API errors (rate limit, server error, timeout) up to 3 attempts.
    - [x] Strict vector dimension validation (ensuring all returned vectors are exactly 1536 floats).
    - [x] Async client lifecycle management and explicit cleanup via `close()`.
  - [x] Integrate with background worker pipeline (`app/tasks/definitions.py`) (Sprint 6.1):
    - [x] Query persisted chunks and invoke `EmbeddingService.embed_chunks` outside of database transactions (Rule A).
    - [x] Whole-document atomic database persistence with verification (Rule B).
    - [x] Advance `Document.status` to `"indexed"` upon successful embedding persistence.
    - [x] Safe failure recording with sanitized `processing_error` in an isolated error transaction.
    - [x] Zero-chunk handling and idempotency protection (skipping already embedded documents).
  - [x] Implement `RetrievalService` (`app/services/retrieval_service.py`) (Sprint 6.2):
    - [x] Structured `RetrievalResult` dataclass preserving metadata, page numbers, and chunk types.
    - [x] In-database pgvector cosine distance calculation ($1 - \text{cosine\_distance}$).
    - [x] Filter by `Chunk.embedding IS NOT NULL`, `Document.status == "indexed"`, optional `document_id`, and `min_similarity`.
    - [x] Deterministic tie-breaking ordering (`similarity DESC, chunk_index ASC, id ASC`).
    - [x] Top-k limiting and parameter validation ($1 \le \text{top\_k} \le 20$, $0.0 \le \text{min\_similarity} \le 1.0$).
  - [x] Add `POST /api/v1/search` developer and retrieval endpoint in `app/api/routes/search.py` (Sprint 6.2).
  - [x] Unit and database integration test suites (`test_embedding_service.py` with 23 tests, `test_retrieval_service.py` with 24 tests) passing with 0 failures (Sprint 6.1 & 6.2).
  - [x] Update E2E test suite (`e2e_test.py`) with PostgreSQL assertions confirming 1536-dimensional embeddings and vector retrieval against indexed financial statements (Sprint 6.1 & 6.2).
* **Files Likely Affected:**
  - `backend/requirements.txt`
  - `backend/app/core/config.py`
  - `backend/app/services/embedding_service.py`
  - `backend/app/services/retrieval_service.py`
  - `backend/app/schemas/search.py`
  - `backend/app/api/routes/search.py`
  - `backend/app/tasks/definitions.py`
  - `backend/tests/test_embedding_service.py`
  - `backend/tests/test_retrieval_service.py`
  - `backend/tests/e2e_test.py`
  - `docs/development/embeddings.md`
  - `docs/development/vector-retrieval.md`
* **Acceptance Criteria:**
  - Every document chunk is embedded with a 1536-dimensional vector stored in `Chunk.embedding`; `Document.status` reaches `"indexed"`; vector search executes inside PostgreSQL using pgvector cosine distance; all 116 regression tests and 5 E2E pipeline scenarios pass cleanly.

---

### Phase 7 — Vector Similarity Search & Index Optimization
* **Goal:** Implement high-performance vector retrieval with HNSW indexing and metadata filtering.
* **Why Needed:** Efficient and accurate chunk retrieval is the foundation of the RAG pipeline.
* **Current Status:** Not Implemented.
* **Tasks:**
  - [ ] Create HNSW vector index migration on `chunks.embedding` using cosine distance (`vector_cosine_ops`):
    ```sql
    CREATE INDEX idx_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
    ```
  - [ ] Implement vector search query service in `RetrieverService` (`app/services/retriever.py`):
    - Cosine similarity query using SQLAlchemy pgvector operator (`Chunk.embedding.cosine_distance(query_embedding)`).
    - Top-k retrieval with similarity threshold score filtering.
    - Metadata filtering (by `document_id`, `chunk_type`, or `page_number`).
* **Files Likely Affected:**
  - `backend/alembic/versions/`
  - `backend/app/services/retriever.py`
* **Acceptance Criteria:**
  - Given a query vector, the system retrieves the top-k most relevant chunks within <50ms with correct distance scores.

---

### Phase 8 — Grounded RAG Query Pipeline
* **Goal:** Build an end-to-end question answering pipeline that generates verifiable, citation-backed answers.
* **Why Needed:** Financial analysts require factually accurate answers citing exact document sections and pages.
* **Current Status:** Not Implemented.
* **Tasks:**
  - [ ] Implement `RAGService` (`app/services/rag_service.py`):
    - Query embedding generation.
    - Semantic context retrieval.
    - Strict financial prompt engineering (demanding strict grounding, disallowing speculation, formatting citations).
    - LLM invocation with OpenAI `gpt-4o` / `gpt-4o-mini`.
  - [ ] Parse and format citations in responses: e.g., `[Doc: Tesla_2023_10K.pdf, Page: 42, Chunk: 12]`.
  - [ ] Implement response fallback when confidence is low or information is not present in the indexed documents.
* **Files Likely Affected:**
  - `backend/app/services/rag_service.py`
  - `backend/app/schemas/query.py`
* **Acceptance Criteria:**
  - Querying "What was the total revenue in 2023?" returns the exact metric accompanied by source document and page citations.

---

### Phase 9 — Multi-Agent Financial Research System (LangGraph)
* **Goal:** Orchestrate specialized AI agents for complex multi-step investment analysis and cross-document synthesis.
* **Why Needed:** Single-turn RAG is insufficient for multi-document comparisons, financial ratio computations, or deep filing audits.
* **Current Status:** Not Implemented (`app/agents/` is an empty package).
* **Tasks:**
  - [ ] Add `langgraph` and `langchain-core` to `backend/requirements.txt`.
  - [ ] Define multi-agent state schema (`ResearchState` containing query, retrieved evidence, numerical analysis, audit notes, final report).
  - [ ] Implement individual agent nodes:
    - **Retriever Agent:** Dispatches sub-queries across multiple documents.
    - **Financial Analyzer Agent:** Extracts numerical figures and calculates financial ratios/trends.
    - **Critic / Verification Agent:** Verifies that every claim and number in the output matches retrieved source chunks.
    - **Writer Agent:** Synthesizes structured markdown research notes with executive summaries and tables.
  - [ ] Compile LangGraph state graph with conditional routing and error handling.
* **Files Likely Affected:**
  - `backend/requirements.txt`
  - `backend/app/agents/state.py`
  - `backend/app/agents/nodes/`
  - `backend/app/agents/orchestrator.py`
* **Acceptance Criteria:**
  - Complex queries (e.g., "Compare gross margin trends between 2022 and 2023 across uploaded 10-Ks") execute through the agent workflow and produce verified, cross-cited reports.

---

### Phase 10 — Query & Report API Endpoints
* **Goal:** Expose RESTful endpoints for interactive queries and long-form research report generation.
* **Why Needed:** Provide the client layer with full access to RAG and multi-agent capabilities.
* **Current Status:** Not Implemented (`Report` model exists; no routes or schemas exist).
* **Tasks:**
  - [ ] Create Pydantic schemas: `QueryRequest`, `QueryResponse`, `ReportCreateRequest`, `ReportResponse` (`app/schemas/query.py`, `app/schemas/report.py`).
  - [ ] Implement query route (`app/api/routes/query.py`):
    - `POST /api/v1/query` (Synchronous or streaming RAG response with citations).
  - [ ] Implement report route (`app/api/routes/reports.py`):
    - `POST /api/v1/reports` (Initiates asynchronous multi-agent research).
    - `GET /api/v1/reports/{report_id}` (Fetches generated report status and content).
    - `GET /api/v1/reports` (List historic reports).
  - [ ] Register new routers in `app/main.py`.
* **Files Likely Affected:**
  - `backend/app/schemas/query.py`
  - `backend/app/schemas/report.py`
  - `backend/app/api/routes/query.py`
  - `backend/app/api/routes/reports.py`
  - `backend/app/main.py`
* **Acceptance Criteria:**
  - Endpoints validated with interactive Swagger documentation (`/docs`) returning properly typed responses.

---

### Phase 11 — Frontend Web Application (React / Next.js)
* **Goal:** Build a sleek, modern UI for financial document management, interactive chat with citation viewing, and report inspection.
* **Why Needed:** End-users need an intuitive workspace to upload documents, review financial answers, and inspect source citations.
* **Current Status:** Not Implemented (`frontend/` directory is empty).
* **Tasks:**
  - [ ] Initialize Next.js 14+ (App Router) or Vite React application in `frontend/`.
  - [ ] Implement core views:
    - **Dashboard:** System stats, recent uploads, recent reports.
    - **Document Manager:** Drag-and-drop file upload, processing status badges, file deletion.
    - **Research & Chat Workspace:** Query input, streaming LLM responses, clickable citation drawer highlighting original page text.
    - **Report Viewer:** Render structured markdown reports with export to PDF/Markdown.
  - [ ] Create API client service connecting to `http://localhost:8000/api/v1`.
  - [ ] Add Dockerfile and docker-compose service configuration for frontend.
* **Files Likely Affected:**
  - `frontend/package.json`
  - `frontend/src/`
  - `docker-compose.yml`
* **Acceptance Criteria:**
  - User can upload a PDF, monitor indexing progress, submit queries, and click citations to view evidence.

---

### Phase 12 — Comprehensive Testing Suite
* **Goal:** Establish automated unit, integration, and evaluation tests.
* **Why Needed:** Ensure extraction accuracy, prevent regressions, and validate mathematical correctness of financial analysis.
* **Current Status:** Not Implemented (No `tests/` directory).
* **Tasks:**
  - [ ] Setup `pytest`, `pytest-asyncio`, and `httpx` test harness with test database fixtures (`backend/tests/conftest.py`).
  - [ ] Unit tests:
    - `test_document_service.py` (File validation, upload, DB operations).
    - `test_pdf_parser.py` (Text extraction, page counts).
    - `test_table_extractor.py` (Table markdown conversion).
    - `test_chunker.py` (Token sizing, metadata tagging).
  - [ ] Integration tests:
    - `test_api_documents.py` (Full upload-to-delete lifecycle).
    - `test_api_query.py` (Vector retrieval and RAG response flow).
  - [ ] Evaluation dataset:
    - Add sample SEC filing excerpts in `tests/fixtures/` and assert citation precision.
* **Files Likely Affected:**
  - `backend/tests/conftest.py`
  - `backend/tests/unit/`
  - `backend/tests/integration/`
  - `backend/tests/fixtures/`
* **Acceptance Criteria:**
  - All test suites run and pass via `pytest` with >80% code coverage.

---

### Phase 13 — Security, Validation & Guardrails
* **Goal:** Harden the system against malicious uploads, prompt injections, and unsecured access.
* **Why Needed:** Financial documents may contain untrusted text or sensitive enterprise data.
* **Current Status:** Basic file extension and size checks implemented.
* **Tasks:**
  - [ ] Add rate limiting middleware to API routes.
  - [ ] Implement prompt injection guardrails on document text before passing into LLM context.
  - [ ] Sanitize file paths and ensure no directory traversal vulnerability exists in storage services.
  - [ ] Enforce environment secret management and prevent hardcoded defaults in production mode.
* **Files Likely Affected:**
  - `backend/app/core/config.py`
  - `backend/app/api/middleware.py`
  - `backend/app/services/document_service.py`
* **Acceptance Criteria:**
  - Malformed files, oversized payloads, and prompt injection attempts are caught and safely rejected.

---

### Phase 14 — Observability, Logging & Cost Tracking
* **Goal:** Implement structured logging, tracing, and token/cost telemetry.
* **Why Needed:** Monitor production health, debug retrieval failures, and track OpenAI API spend.
* **Current Status:** Basic console `print()` calls in `main.py`.
* **Tasks:**
  - [ ] Replace `print` statements with structured JSON logging (`structlog` or standard `logging`).
  - [ ] Track embedding and LLM token usage per document and per query.
  - [ ] Add detailed health check endpoint (`/health`) verifying PostgreSQL and Redis connectivity.
* **Files Likely Affected:**
  - `backend/app/core/logging.py`
  - `backend/app/main.py`
  - `backend/app/services/embedding_service.py`
  - `backend/app/services/rag_service.py`
* **Acceptance Criteria:**
  - API outputs structured logs with request IDs, database health status, and LLM token consumption metrics.

---

### Phase 15 — Production Containerization & Deployment
* **Goal:** Prepare production-ready Docker builds, environment manifests, and automated CI/CD.
* **Why Needed:** Ensure predictable, reproducible deployments in production cloud environments.
* **Current Status:** Development Docker Compose exists; GitHub Actions has `release-please.yml`.
* **Tasks:**
  - [ ] Create multi-stage production `Dockerfile` for backend (non-root user, slim base).
  - [ ] Configure production `docker-compose.prod.yml` with persistent volume management and resource constraints.
  - [ ] Add CI workflow (`.github/workflows/ci.yml`) for linting (`ruff`/`black`), type checking (`mypy`), and test execution.
  - [ ] Document production backup and restore procedures for PostgreSQL pgvector data.
* **Files Likely Affected:**
  - `backend/Dockerfile`
  - `docker-compose.prod.yml`
  - `.github/workflows/ci.yml`
* **Acceptance Criteria:**
  - Clean CI pipeline runs tests on pull requests; production containers build with minimal attack surface.

---

### Phase 16 — Comprehensive Documentation
* **Goal:** Provide thorough developer and user documentation.
* **Why Needed:** Ensure onboarding ease, API discoverability, and architectural transparency.
* **Current Status:** Basic `README.md` exists with conceptual overview.
* **Tasks:**
  - [ ] Update `README.md` with current quickstart instructions, environment variable descriptions, and feature progress.
  - [ ] Create `docs/architecture.md` detailing multi-agent flow, pgvector indexing, and chunking strategies.
  - [ ] Create `docs/api.md` with example payloads for all REST endpoints.
* **Files Likely Affected:**
  - `README.md`
  - `docs/architecture.md`
  - `docs/api.md`
* **Acceptance Criteria:**
  - A new developer can clone the repo, start the containers, run tests, and execute a query within 10 minutes following the docs.
