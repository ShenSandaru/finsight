# Database Migrations Guide (Alembic) — FinSight

This document details the database migration architecture, workflows, and best practices for **FinSight**.

---

## 1. Overview & Architecture

FinSight uses **Alembic** alongside **SQLAlchemy 2.0 (asyncpg)** and **pgvector** to manage PostgreSQL database schema evolution.

### Key Rules
- **FastAPI startup does NOT run `Base.metadata.create_all()`**. The application assumes the database schema is managed and migrated externally via Alembic.
- **pgvector Extension:** PostgreSQL initializes the `vector` extension via `scripts/init.sql` upon container creation (`CREATE EXTENSION IF NOT EXISTS vector;`).
- **Alembic Location:** All migration scripts and configurations reside directly in the backend directory:
  - Configuration: `finsight/backend/alembic.ini`
  - Environment script: `finsight/backend/alembic/env.py`
  - Migration script template: `finsight/backend/alembic/script.py.mako`
  - Revisions directory: `finsight/backend/alembic/versions/`

---

## 2. Database Connection Configuration

Alembic pulls connection parameters dynamically from `app.core.config.get_settings()` inside `alembic/env.py`. It uses the exact same `DATABASE_URL` environment variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`) configured in `.env`.

---

## 3. Migration Workflows & Commands

All Alembic commands must be run from inside the `finsight/backend/` directory or inside the `finsight_backend` container.

### A. Inside the Docker Container (Recommended)

To execute migrations directly in the containerized environment:

```bash
# Apply all pending migrations to head
docker compose exec backend alembic upgrade head

# Rollback the last migration
docker compose exec backend alembic downgrade -1

# Show current database revision
docker compose exec backend alembic current

# Show migration history
docker compose exec backend alembic history

# Generate a new migration after updating ORM models
docker compose exec backend alembic revision --autogenerate -m "describe_change"
```

### B. Local Terminal Workflow (from `finsight/backend/`)

If running locally with PostgreSQL accessible on `localhost:5432`:

```bash
cd finsight/backend

# Upgrade database to latest revision
alembic upgrade head

# Downgrade 1 revision
alembic downgrade -1

# Check current revision status
alembic current

# View history
alembic history

# Autogenerate migration
alembic revision --autogenerate -m "describe_change"
```

---

## 4. Initial Schema Migration

The initial baseline migration is `0001_initial_schema.py`, defining the exact structure of:
1. **`documents` table:** UUID primary key, file metadata, status (`pending`), page/chunk counters, timestamps.
2. **`chunks` table:** UUID primary key, `document_id` FK (with `CASCADE` delete), `content`, `embedding` (`Vector(1536)`), `chunk_type`, `chunk_index`, `page_number`, and `metadata` (JSONB).
3. **`reports` table:** UUID primary key, `query`, `response`, `sources` (JSONB), `report_type`, `status`, and timestamps.
