from functools import lru_cache
from pathlib import Path
from typing import Union
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "FinSight"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    WEB_CONCURRENCY: int = 1

    # Security & CORS
    CORS_ORIGINS: Union[list[str], str] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, list[str]]) -> list[str]:
        if isinstance(v, str):
            origins = [origin.strip() for origin in v.split(",") if origin.strip()]
            return origins or ["http://localhost:3000"]
        return v

    # Authentication & Sessions
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8888/api/v1/auth/google/callback"
    SESSION_SECRET_KEY: str = "dev-session-secret-key-change-in-production"
    SESSION_COOKIE_NAME: str = "finsight_session"
    SESSION_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 7  # 7 days (604800 seconds)
    SESSION_COOKIE_SECURE: bool = False
    OAUTH_STATE_COOKIE_NAME: str = "finsight_oauth_state"
    OAUTH_STATE_MAX_AGE_SECONDS: int = 300  # 5 minutes
    FRONTEND_URL: str = "http://localhost:3000"
    SYSTEM_USER_ID: str = "00000000-0000-0000-0000-000000000001"

    @field_validator("SESSION_COOKIE_SECURE", mode="after")
    @classmethod
    def validate_cookie_security(cls, v: bool, info) -> bool:
        debug = info.data.get("DEBUG", True)
        if not debug and not v:
            raise ValueError(
                "Insecure session cookie configuration: SESSION_COOKIE_SECURE must be True when DEBUG is False in production."
            )
        return v

    # PostgreSQL
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432

    # Redis & Task Queue
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    ARQ_QUEUE_NAME: str = "finsight_tasks"
    TASK_MAX_TRIES: int = 3
    TASK_TIMEOUT_SECONDS: int = 300

    # Gemini & Embedding Configuration
    GEMINI_API_KEY: str = ""
    EMBEDDING_PROVIDER: str = "gemini"  # "gemini" or "fake" (for testing)
    EMBEDDING_MODEL: str = "gemini-embedding-2"
    EMBEDDING_DIMENSIONS: int = 1536
    EMBEDDING_BATCH_SIZE: int = 50
    EMBEDDING_MAX_RETRIES: int = 3
    EMBEDDING_TIMEOUT_SECONDS: float = 60.0

    # Retrieval Configuration
    RETRIEVAL_DEFAULT_TOP_K: int = 5
    RETRIEVAL_MAX_TOP_K: int = 20
    RETRIEVAL_MIN_SIMILARITY: float = 0.0

    # pgvector HNSW Configuration
    HNSW_ENABLED: bool = True
    HNSW_M: int = 16
    HNSW_EF_CONSTRUCTION: int = 64
    HNSW_EF_SEARCH: int = 40

    # Retrieval Benchmark Configuration
    RETRIEVAL_BENCHMARK_TOP_K: int = 5
    RETRIEVAL_BENCHMARK_QUERIES: int = 20
    RETRIEVAL_RECALL_TARGET: float = 0.95

    # RAG Configuration
    RAG_DEFAULT_TOP_K: int = 5
    RAG_MAX_TOP_K: int = 20
    RAG_MAX_CONTEXT_CHARS: int = 18000
    RAG_MIN_RELEVANCE_SCORE: float = 0.30

    # Conversation Configuration
    CONVERSATION_MAX_HISTORY_MESSAGES: int = 10
    CONVERSATION_MAX_MESSAGE_CHARS: int = 8000
    CONVERSATION_MAX_SESSIONS_MESSAGES: int = 100
    CONVERSATION_FOLLOWUP_REWRITE_ENABLED: bool = True

    # Multi-Agent Research Configuration (Sprint 9.1)
    AGENT_MAX_SUBQUERIES: int = 4
    AGENT_MAX_STEPS: int = 6
    AGENT_ANALYZER_CONFIDENCE_THRESHOLD: float = 0.50

    # Guardrails AI Configuration (Sprint 9.2)
    GUARDRAILS_ENABLED: bool = True
    GUARDRAILS_STRICT_CITATION_CHECK: bool = True
    GUARDRAILS_MAX_RESPONSE_LENGTH: int = 10000

    # Gemini Generation Configuration
    GEMINI_GENERATION_PROVIDER: str = "gemini"  # "gemini" or "fake" (for testing)
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MAX_OUTPUT_TOKENS: int = 1200
    GEMINI_TEMPERATURE: float = 0.1
    GEMINI_MAX_RETRIES: int = 3
    GEMINI_GENERATION_TIMEOUT_SECONDS: float = 60.0

    # File Storage
    STORAGE_PATH: Path = Path("/app/storage")
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB in bytes
    ALLOWED_FILE_TYPES: list[str] = ["pdf", "txt", "csv"]

    # Chunking Configuration
    DEFAULT_CHUNK_SIZE: int = 1200
    DEFAULT_CHUNK_OVERLAP: int = 150

    # Rate Limiting & Abuse Protection (Phase 12.3)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH: str = "10/60"               # 10 req / 60 sec (Google login/callback)
    RATE_LIMIT_RAG: str = "20/60"                # 20 req / 60 sec (LLM RAG queries)
    RATE_LIMIT_SEARCH: str = "30/60"             # 30 req / 60 sec (Vector similarity search)
    RATE_LIMIT_REPORTS: str = "5/60"             # 5 req / 60 sec (Prevents background job amplification)
    RATE_LIMIT_DOCUMENT_UPLOAD: str = "10/60"    # 10 uploads / 60 sec
    RATE_LIMIT_CONVERSATION_QUERY: str = "20/60" # 20 req / 60 sec
    RATE_LIMIT_GENERAL: str = "100/60"           # 100 req / 60 sec (General authenticated reads)

    @field_validator(
        "RATE_LIMIT_AUTH",
        "RATE_LIMIT_RAG",
        "RATE_LIMIT_SEARCH",
        "RATE_LIMIT_REPORTS",
        "RATE_LIMIT_DOCUMENT_UPLOAD",
        "RATE_LIMIT_CONVERSATION_QUERY",
        "RATE_LIMIT_GENERAL",
        mode="after",
    )
    @classmethod
    def validate_rate_limit_format(cls, v: str) -> str:
        parts = v.strip().split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid rate limit format '{v}'. Expected format: '<requests>/<window_seconds>' e.g. '20/60'")
        try:
            reqs, window = int(parts[0]), int(parts[1])
            if reqs <= 0 or window <= 0:
                raise ValueError()
        except ValueError:
            raise ValueError(f"Invalid rate limit values in '{v}'. Both requests and window_seconds must be positive integers.")
        return v

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}"
            f":{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}"
            f":{self.POSTGRES_PORT}"
            f"/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    @property
    def DOCUMENTS_PATH(self) -> Path:
        return self.STORAGE_PATH / "documents"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()