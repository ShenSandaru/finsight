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

    # OpenAI
    OPENAI_API_KEY: str = ""

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()