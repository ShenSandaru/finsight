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
- `CORS_ORIGINS`: Comma-separated list of allowed origins (e.g. `http://localhost:3000,https://finsight.company.com`). Never uses `*` by default.
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
# Backend liveness
curl http://localhost:8000/health

# Frontend response
curl -I http://localhost:3000/
```

---

## 5. Storage & Persistence Notes

- **Database**: Saved in persistent named volume `postgres_data`.
- **Redis**: Saved in persistent named volume `redis_data` with `--appendonly yes`.
- **Documents**: Uploaded PDFs and text files are stored in the named volume `finsight_storage` mounted at `/app/storage`. Both the backend and worker mount this shared volume.
- **Single-Host Architecture**: In Phase 12.1, `finsight_storage` is a Docker local named volume. Multi-node cloud object storage (S3/GCS) is planned for a subsequent phase.
