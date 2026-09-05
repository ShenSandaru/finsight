FROM python:3.11-slim

# Set environment variables for Python in container
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    WEB_CONCURRENCY=1

WORKDIR /app

# Install minimal runtime system dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user and group
RUN groupadd --gid 10001 appuser && \
    useradd --uid 10001 --gid appuser --shell /bin/bash --create-home appuser

# Install Python dependencies first (leverage Docker build cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=120 -r requirements.txt

# Copy application source code
COPY app/ /app/app/
COPY alembic.ini /app/alembic.ini

# Ensure storage directories exist and assign ownership to appuser
RUN mkdir -p /app/storage/documents && \
    chown -R appuser:appuser /app

# Expose FastAPI application port
EXPOSE 8000

# Container healthcheck testing the liveness endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run as non-root user
USER appuser

# Production startup using uvicorn with WEB_CONCURRENCY support via sh -c
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-1}"]