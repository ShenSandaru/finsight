# FinSight 🔍📈

FinSight is a robust application designed to ingest, process, and analyze documents (such as financial reports) using AI agents and vector-based search. It leverages a modern Python backend, a vector-enabled PostgreSQL database, and Redis for performance and asynchronous processing.

## 🎯 Purpose and How it Works

The core purpose of FinSight is to handle large documents, break them down into manageable pieces (chunks), and use AI-driven agents to retrieve insights from them. 

**Workflow:**
1. **Document Ingestion:** Users upload documents via the backend API.
2. **Processing & Chunking:** The `document_service` processes the files, extracting text and splitting them into smaller data `chunks`.
3. **Vectorization:** These chunks are converted into embeddings and stored in PostgreSQL using the `pgvector` extension for semantic search capabilities.
4. **Agent Analysis:** Dedicated AI agents interact with the vector database to answer queries, generate reports, or extract specific financial insights.

## 🛠️ Technologies Used

* **Backend:** Python (structured for modern frameworks like FastAPI)
* **Database:** PostgreSQL (with `pgvector` extension for AI/embedding storage)
* **Caching/Queue:** Redis (for fast data retrieval and async task tracking)
* **Containerization:** Docker & Docker Compose
* **Frontend:** (Setup in progress)

## 📂 Project Structure

```text
finsight/
├── backend/                  # Core API and AI logic
│   ├── app/
│   │   ├── agents/           # AI interaction agents
│   │   ├── api/routes/       # API definition (e.g., documents.py)
│   │   ├── core/             # DB config, environment vars
│   │   ├── models/           # DB tables (document, chunk, report)
│   │   ├── schemas/          # Pydantic validation models
│   │   └── services/         # Business logic (document processing)
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

*   **Backend API:** `http://localhost:8000` (e.g., `http://localhost:8000/docs` for API documentation)
*   **PostgreSQL:** `localhost:5432`
*   **Redis:** `localhost:6379`

## 📝 Future Development

- [ ] Implement the `frontend` architecture.
- [ ] Expand AI agent capabilities.
- [ ] Implement robust user authentication.


