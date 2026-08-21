from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "FinSight"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

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