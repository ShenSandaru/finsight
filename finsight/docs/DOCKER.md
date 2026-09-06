# FinSight Docker & Environment Operations Guide

This guide describes development and production container operations for FinSight.

---

## 1. Architecture Overview

FinSight services:
- **Frontend**: Next.js 14 standalone multi-stage container (`node:20-alpine`, non-root user `nextjs`).
- **Backend**: FastAPI asynchronous REST API (`python:3.11-slim`, non-root user `appuser`).
- **Worker**: ARQ background task processor running `app.worker.WorkerSettings`.
- **Database**: PostgreSQL 16 with `pgvector/pgvector:pg16` extension.
- **Cache & Queue**: Redis 7 with Append-Only File (AOF) persistence.

---

## 2. Development Environment

The development stack retains live-reload and source directory bind-mounts:

### Starting Development Stack
```bash
docker compose up -d
```

### Stopping Development Stack
```bash
docker compose down
```

### Viewing Logs
```bash
docker compose logs -f backend
docker compose logs -f worker
```

---

## 3. Production Environment

The production stack (`docker-compose.prod.yml`) runs immutable, optimized containers with zero application source mounts.

### Production Environment Variables
Copy `.env.example` to `.env` on your target server and provide production credentials:

```bash
cp .env.example .env
```

Key environment variables:
- `ENVIRONMENT`: Deployment environment (`development` | `production`). When set to `production`, `DEBUG` must be `false` and production session secrets must not use placeholders.
- `ALLOWED_HOSTS`: Comma-separated list of trusted Host headers (e.g. `localhost,127.0.0.1,api.finsight.company.com`). Rejects requests with spoofed or untrusted Host headers.
- `CORS_ORIGINS`: Comma-separated list of allowed origins (e.g. `http://localhost:3000,https://finsight.company.com`). Never uses `*` when credentials/cookies are enabled.
- `WEB_CONCURRENCY`: Uvicorn workers per backend container (defaults to `1` to avoid redundant ARQ connection pools; horizontal scaling should be performed via container replication).
- `BACKEND_PORT`: Host port bound to FastAPI (defaults to `8000`).
- `FRONTEND_PORT`: Host port bound to Next.js (defaults to `3000`).
- `NEXT_PUBLIC_API_URL`: **Build-time** URL used by the browser to reach the backend API. Because Next.js bakes `NEXT_PUBLIC_*` variables into client-side JS bundles during build time, changes to this value require rebuilding the frontend image.

### Building Production Images
```bash
docker compose -f docker-compose.prod.yml build
```

To build with a specific public API endpoint:
```bash
docker compose -f docker-compose.prod.yml build --build-arg NEXT_PUBLIC_API_URL=https://api.finsight.company.com frontend
```

### Starting Production Stack
```bash
docker compose -f docker-compose.prod.yml up -d
```

### Stopping Production Stack
```bash
docker compose -f docker-compose.prod.yml down
```

To remove containers and preserve volumes:
```bash
docker compose -f docker-compose.prod.yml stop
```

### Viewing Logs
```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f worker
docker compose -f docker-compose.prod.yml logs -f frontend
```

---

## 4. Health Checks & Verification

### Container Health Status
```bash
docker compose -f docker-compose.prod.yml ps
```

All health-monitored services will show `(healthy)`:
- `postgres`: Checked via `pg_isready`.
- `redis`: Checked via `redis-cli ping`.
- `backend`: Checked via `curl -f http://localhost:8000/health`.
- `frontend`: Checked via `wget --spider http://localhost:3000/`.
- `worker`: **Note on Worker Monitoring**: The worker is an async task consumer process listening to Redis. It has no HTTP listener, so it intentionally does not expose an HTTP healthcheck. Worker liveness is monitored via ARQ Redis heartbeats, container process supervision, and log output (`docker compose -f docker-compose.prod.yml logs worker`).

### Manual Health Probes
```bash
# Backend liveness (process alive, no DB/Redis dependency)
curl http://localhost:8000/health

# Backend readiness (dependency probe: verifies PostgreSQL and Redis connectivity)
curl http://localhost:8000/ready

# Frontend response
curl -I http://localhost:3000/
```

---

## 5. Storage & Persistence Notes

- **Database**: Saved in persistent named volume `postgres_data`.
- **Redis**: Saved in persistent named volume `redis_data` with `--appendonly yes`.
- **Documents**: Uploaded PDFs and text files are stored in the named volume `finsight_storage` mounted at `/app/storage`. Both the backend and worker mount this shared volume.
- **Single-Host Architecture**: In Phase 12.1, `finsight_storage` is a Docker local named volume. Multi-node cloud object storage (S3/GCS) is planned for a subsequent phase.

---

## 6. Observability & Structured Logging (Phase 12.5)

FinSight features a native, lightweight structured logging and request correlation architecture without external dependencies.

### Environment Configuration
- `LOG_LEVEL`: `DEBUG` | `INFO` (default) | `WARNING` | `ERROR` | `CRITICAL`
- `LOG_FORMAT`: `json` (default for production container) | `text` (human-readable for development)

### Request Tracing & Correlation
- All inbound requests accept an optional `X-Request-ID` header (max 64 alphanumeric characters, `-` and `_`).
- If omitted or invalid, the backend generates a cryptographically secure UUID4.
- The canonical request ID is bound to a Python `contextvars.ContextVar` across the request lifecycle and returned in the `X-Request-ID` response header.

### Sensitive Data Exclusion
To protect confidentiality and financial privacy, logs **never** contain:
- Authorization headers, access tokens, refresh tokens, or API keys
- Session cookies or OAuth state tokens
- Query strings (e.g. `/api/v1/auth/google/callback` omits `code` and `state` parameters)
- Request bodies, raw prompts, or full LLM generated responses
- Uploaded document contents or extracted chunk text

### Viewing Logs with Docker
```bash
# Production JSON log inspection with jq
docker compose -f docker-compose.prod.yml logs -f backend | jq .

# Filter by specific request correlation ID
docker compose -f docker-compose.prod.yml logs backend | jq 'select(.request_id == "01H...")'

# Worker task processing logs
docker compose -f docker-compose.prod.yml logs -f worker
```
