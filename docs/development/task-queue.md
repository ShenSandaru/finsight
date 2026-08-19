# Async Task Queue Architecture (ARQ + Redis) — FinSight

This document details the architecture, design decisions, configuration, and worker workflows for FinSight's background task queue.

---

## 1. Technology Selection: ARQ + Redis

### Why ARQ?
For FinSight's AI ingestion pipeline (document parsing, financial table extraction, chunking, and embedding generation), we evaluated **Celery** vs. **ARQ**:

1. **Async-Native:** ARQ is built on top of `asyncio` and `redis-py` (async), integrating directly with FastAPI's event loop and SQLAlchemy 2.0's async sessions without requiring complex event loop thread bridging.
2. **Lightweight & Maintainable:** ARQ has zero dependencies outside `redis` and `pydantic`. Celery brings heavy sub-dependencies (Kombu, billiard, vine, amqp) and legacy synchronous designs.
3. **Pydantic Validation & Typing:** Job parameters and payloads are cleanly handled.
4. **Graceful Concurrency & Health:** Handles worker task timeouts, job retries, and shutdown signals out of the box.

---

## 2. Component Architecture

```
FastAPI Backend (app.api)
    │
    ▼
app.core.tasks (enqueue_task)
    │
    ▼
Redis (Container: finsight_redis, Port: 6379, Queue: finsight_tasks)
    │
    ▼
ARQ Worker (Container: finsight_worker, Entrypoint: app.worker.WorkerSettings)
    │
    ▼
app.tasks.definitions (health_check_task, failing_test_task, etc.)
```

- **Client (`app/core/tasks.py`):** Manages a singleton `ArqRedis` connection pool, enqueuing jobs to the `finsight_tasks` Redis queue.
- **Worker (`app/worker.py`):** Starts an independent process consuming jobs from `finsight_tasks`.
- **Definitions (`app/tasks/definitions.py`):** Houses pure async task functions.
- **Docker Isolation:** The API server (`finsight_backend`) and background worker (`finsight_worker`) run as separate containers sharing the same codebase and Redis instance.

---

## 3. Configuration Parameters

Configured via `app.core.config.Settings` (overridable in `.env`):

| Setting | Default Value | Description |
| :--- | :--- | :--- |
| `REDIS_HOST` | `redis` | Redis service hostname in Docker |
| `REDIS_PORT` | `6379` | Redis service port |
| `ARQ_QUEUE_NAME` | `finsight_tasks` | Default task queue key in Redis |
| `TASK_MAX_TRIES` | `3` | Maximum automatic retries for transient job failures |
| `TASK_TIMEOUT_SECONDS`| `300` | 5-minute task execution timeout |

---

## 4. Running & Monitoring the Worker

### Docker Compose
The worker runs automatically as part of `docker-compose.yml`:
```powershell
# Start all services (PostgreSQL, Redis, Backend, Worker)
docker compose up -d

# View real-time worker logs
docker compose logs -f worker
```

### Local Manual Execution
To run the worker locally outside Docker:
```powershell
cd finsight/backend
arq app.worker.WorkerSettings
```

---

## 5. Document Ingestion Pipeline Flow (Sprint 2.1)

```
Client (POST /api/v1/documents/upload)
    │
    ▼
1. Validation (extension check + size limit + magic-byte content validation)
    │
    ▼
2. Safe Disk Storage (UUID-prefixed, sanitized base filename)
    │
    ▼
3. Create Document DB record with status = "pending"
    │
    ▼
4. COMMIT Database Transaction (ensures record is durable in PostgreSQL)
    │
    ▼
5. Enqueue ARQ task: process_document(document.id) -> Redis ('finsight_tasks')
    │
    ▼
6. Return HTTP 201 Created to Client immediately (asynchronous response)
    │
    ▼
[Out-of-band Background Worker]
ARQ Worker picks up process_document
    │
    ▼
Checks idempotency: status == "pending"?
    │
    ├── Yes: Sets status = "processing", clears processing_error, commits DB
    └── No:  Logs and skips duplicate processing
```

### Database vs. Queue Consistency Guarantee
To prevent race conditions where a worker attempts to process a document that is not yet visible in PostgreSQL, FinSight enforces strict ordering:
1. `db.commit()` **MUST always precede** `enqueue_task()`.
2. If `enqueue_task()` raises an error after DB commit (e.g. Redis unavailable), the API raises `ExternalServiceError(503)` while retaining the document in `status="pending"`. The document record remains preserved and recoverable in PostgreSQL.

---

## 6. Test Tasks & Verification

Test endpoints are exposed in `app/api/routes/tasks.py` for infrastructure health verification:

1. **Success Verification:** `POST /api/v1/tasks/test-health`
   - Enqueues `health_check_task` with a test payload.
   - Worker picks up job, records duration, and logs successful completion.
2. **Failure Resilience Verification:** `POST /api/v1/tasks/test-failure`
   - Enqueues `failing_test_task` raising `RuntimeError`.
   - Worker captures and logs traceback with error details without crashing the worker process.
