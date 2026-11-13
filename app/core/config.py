from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Empty values in .env (placeholders like `EMBEDDING_MODEL=`) fall back to the defaults below.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "postgresql+asyncpg://trace:trace@localhost:5433/trace"
    log_level: str = "INFO"
    rate_limit_per_min: int = 30

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # BGE models are trained with this instruction on the query side only.
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "
    model_cache_dir: str = "data/models"

    # Which ingested repository the API answers from.
    corpus_repo_id: str = "https://github.com/vitejs/vite"

    # Any OpenAI-compatible chat completions endpoint (most hosted free tiers offer one).
    llm_base_url: str = ""
    llm_model: str = ""  # pin an exact model version where the provider allows it
    llm_api_key: SecretStr = SecretStr("")
    llm_requests_per_minute: float = 10
    llm_cache_dir: str = "data/llm_cache"  # empty string disables the response cache

    @property
    def sync_database_url(self) -> str:
        """SQLAlchemy URL using the psycopg driver (used by Alembic)."""
        return self.database_url.replace("+asyncpg", "+psycopg")

    @property
    def psycopg_dsn(self) -> str:
        """Plain libpq-style URL for direct psycopg connections (used by tests)."""
        return self.database_url.replace("+asyncpg", "").replace("+psycopg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
