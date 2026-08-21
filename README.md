# FinSight 🔍📈

FinSight is a robust application designed to ingest, process, and analyze documents (such as financial reports) using AI agents and vector-based search. It leverages a modern Python backend, a vector-enabled PostgreSQL database, and Redis for performance and asynchronous processing.

## 🎯 Purpose and How it Works

FinSight enables automated financial research, multi-turn conversational analysis, and deep filing audits with strict grounding guarantees.

**Workflow:**
1. **Multi-Format Ingestion:** Ingests PDF, TXT, and CSV documents with magic-byte validation.
2. **Table Extraction & Classification:** Extracts financial tables via `pdfplumber` and applies deterministic semantic classification (`income_statement`, `balance_sheet`, `cash_flow`, fiscal periods).
3. **Table-Aware Chunking:** Chunks text and tables while preserving structured Markdown representations and JSONB metadata.
4. **Vector Embedding & HNSW Indexing:** Converts chunks into 1536-dimensional vectors using Google Gemini (`gemini-embedding-2`) and indexes them in PostgreSQL with pgvector HNSW cosine search.
5. **Conversational Memory & Query Rewriting:** Manages isolated conversation sessions and deterministically rewrites pronoun-dependent follow-up queries.
6. **LangGraph Multi-Agent Research:** Orchestrates a 5-node DAG (`Planner -> Retriever -> Financial Analyzer -> Citation Auditor -> Synthesis`) calculating financial ratios determinist17. **Deterministic Output Validation (Guardrails):** Enforces Pydantic v2 runtime constraints, validating output structure, citation provenance, numerical bounds, and grounding guarantees before client delivery.
18. **Extended Financial Metrics & Multi-Period Analysis:** Deterministically calculates Operating Margin, ROA, Current Ratio, Debt-to-Equity, Free Cash Flow, sequential YoY growth, and multi-year CAGR with trend classifications.
19. **Multi-Document & Cross-Company Comparison:** Scopes vector retrieval and metric isolation across multiple corporate filings with deterministic variance analysis.
20. **Asynchronous Structured Research Reports:** Generates exportable, publication-ready GitHub Flavored Markdown research reports via ARQ background workers with full source provenance.

## 🛠️ Technologies Used

* **Backend Framework:** Python 3.11, FastAPI, SQLAlchemy 2.0 (Async), Alembic
* **Database & Search:** PostgreSQL 16, pgvector (1536-dim vector embeddings, HNSW index)
* **Caching & Background Queue:** Redis 7, ARQ async worker
* **AI & Multi-Agent Orchestration:** Google Gemini 2.0 Flash, Gemini Embeddings, LangGraph, LangChain Core
* **Validation & Safety:** Pydantic v2, Custom Deterministic Guardrails Layer
* **Document Processing:** pypdf, pdfplumber
* **Containerization:** Docker & Docker Compose
* **Frontend:** (Planned)

## 📂 Project Structure

```text
finsight/
├── backend/                  # Core API and AI logic
│   ├── app/
│   │   ├── agents/           # LangGraph multi-agent nodes & graph
│   │   ├── api/routes/       # API endpoints (documents, search, rag, conversations, reports)
│   │   ├── core/             # DB config, environment vars, tasks
│   │   ├── guardrails/       # Deterministic safety & citation validators
│   │   ├── models/           # DB tables (document, chunk, conversation, report)
│   │   ├── schemas/          # Pydantic validation models
│   │   └── services/         # Business logic (retrieval, generation, conversation, report)
│   ├── storage/              # Local storage for raw uploaded files
│   ├── Dockerfile            # Backend container configuration
│   └── requirements.txt      # Python dependencies
├── frontend/                 # UI Application (pending)
├── scripts/                  # DB init scripts (init.sql)
├── docker-compose.yml        # Multi-container orchestration
└── .env                      # Environment variables (Credentials)
```

## 🚀 Getting Started

Follow these instructions to set up and run the FinSight project on your local machine.

### Prerequisites

*   [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed on your machine.
*   A `.env` file created in the `finsight` directory (alongside `docker-compose.yml`) containing database and application variables:

    ```env
    # Example .env
    POSTGRES_USER=finsight_user
    POSTGRES_PASSWORD=yourpassword
    POSTGRES_DB=finsight_db
    # Add other necessary variables like OpenAI API keys if needed
    ```

### Running the Project

1.  **Navigate to the core project directory:**
    ```bash
    cd finsight
    ```

2.  **Build and start the application:**
    Run the following command to download images, build the backend, and start the services.
    ```bash
    docker compose up --build
    ```

3.  **Running in the background:**
    If you want the containers to run in the background (detached mode), use:
    ```bash
    docker compose up -d --build
    ```

4.  **Stopping the application:**
    To stop the running containers, press `Ctrl+C` (if running in the foreground), or run:
    ```bash
    docker compose down
    ```

## 🌐 Services and Ports
 
Once the application is running via Docker Compose, the services will be available at:
 
*   **Backend API:** `http://localhost:8085` (Swagger Docs: `http://localhost:8085/docs`)
*   **PostgreSQL:** `localhost:5432`
*   **Redis:** `localhost:6379`

### Running Automated Tests

```bash
# Run full Pytest regression suite (235 tests)
docker compose exec backend pytest -v

# Run full Docker End-to-End Pipeline (13 Scenarios)
docker compose exec backend python tests/e2e_test.py
```

## 📝 Development Status & Roadmap

| Phase | Milestone | Status |
|---|---|---|
| **Phase 1** | Baseline & Async Task Queue (ARQ + Redis) | ✅ Complete |
| **Phase 2** | Document Ingestion & Validation | ✅ Complete |
| **Phase 3** | PDF, TXT & CSV Parsing | ✅ Complete |
| **Phase 4** | Financial Table Extraction & Semantics | ✅ Complete |
| **Phase 5** | Table-Aware Chunking Strategy | ✅ Complete |
| **Phase 6** | Gemini Embeddings & Vector Retrieval | ✅ Complete |
| **Phase 7** | Grounded Single-Turn RAG + Citations | ✅ Complete |
| **Phase 8** | HNSW Vector Optimization & Conversational Memory | ✅ Complete |
| **Phase 9.1** | LangGraph Multi-Agent Financial Research | ✅ Complete |
| **Phase 9.2** | Deterministic AI Output Validation (Guardrails) | ✅ Complete |
| **Phase 10.1** | Extended Financial Metrics & Ratio Library | ✅ Complete |
| **Phase 10.2** | Multi-Period Sequencing & CAGR Trend Analysis | ✅ Complete |
| **Phase 10.3** | Multi-Document & Cross-Company Comparison | ✅ Complete |
| **Phase 10.4** | Structured Research Reports & REST Endpoints | ✅ Complete |
| **Phase 10.5** | Financial Evaluation & Benchmark Suite | 🔄 Planned / Next |
| **Phase 11** | Frontend Web Application (React / Next.js) | 🔄 Planned |

**Verification Status:**
* **235 Pytest unit & integration tests passing** (100% pass rate).
* **13/13 Docker E2E pipeline scenarios passing**.
* **System Audit Status:** `PRODUCTION-READY FOUNDATION`.**222 Pytest unit & integration tests passing** (100% pass rate).
* **9/9 Docker E2E pipeline scenarios passing**.
* **System Audit Status:** `PRODUCTION-READY FOUNDATION`.
