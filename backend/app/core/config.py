"""Application configuration using Pydantic Settings.

Reads environment variables from .env file or system environment with
validation, type safety, and sensible defaults.
"""

from functools import lru_cache
from typing import Annotated, Any, Union
from pydantic import AnyHttpUrl, BeforeValidator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str]:
    """Parse CORS origins whether provided as a JSON list, comma-separated string, or Python list."""
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list):
        return [str(item) for item in v]
    return v


class Settings(BaseSettings):
    """Central application configuration settings."""

    # Core Application
    PROJECT_NAME: str = "AI Voice Assistant"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # CORS
    BACKEND_CORS_ORIGINS: Annotated[list[str], BeforeValidator(parse_cors)] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # PostgreSQL Database Credentials
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "ai_voice_assistant"

    # Direct database URI override (optional)
    SQLALCHEMY_DATABASE_URI: str | None = None

    # Connection Pool Settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_PRE_PING: bool = True

    # Security & JWT Token Settings (Prepared for future authentication)
    SECRET_KEY: str = "temporary_secret_key_change_in_production_environment"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Return explicit database URL if set; otherwise construct PostgreSQL URL from credentials."""
        if self.SQLALCHEMY_DATABASE_URI:
            return self.SQLALCHEMY_DATABASE_URI
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()


settings = get_settings()
