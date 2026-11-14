"""Application configuration using Pydantic Settings.

Reads environment variables from .env file or system environment with
validation, type safety, and sensible defaults.
"""

from functools import lru_cache
from typing import Annotated, Any, Union
from pydantic import AliasChoices, AnyHttpUrl, BeforeValidator, Field, computed_field, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


def parse_bool(v: Any) -> bool:
    """Safely parse boolean values even if system environment sets non-standard values like 'release'."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "t", "yes", "y", "debug")
    return bool(v)


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
    DEBUG: Annotated[bool, BeforeValidator(parse_bool)] = True
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

    # Initial Super Admin Bootstrap (Phase 8)
    FIRST_SUPERUSER_EMAIL: str = "superadmin@vattara.com"
    FIRST_SUPERUSER_PASSWORD: str | None = None

    # API Rate Limiting Settings (Phase 8)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    RATE_LIMIT_FORGOT_PASSWORD_PER_MINUTE: int = 3
    RATE_LIMIT_RESET_PASSWORD_PER_MINUTE: int = 5

    # Twilio Telephony Settings (Phase 5)
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_PHONE_NUMBER: str | None = None
    PUBLIC_BASE_URL: str | None = None
    NGROK_AUTHTOKEN: str | None = None

    # Plivo Programmable Voice Settings (Primary Indian Telephony)
    PLIVO_AUTH_ID: str | None = None
    PLIVO_AUTH_TOKEN: str | None = None
    PLIVO_PHONE_NUMBER: str | None = None
    PLIVO_APP_ID: str | None = None

    @property
    def is_plivo_configured(self) -> bool:
        """Check whether essential Plivo credentials are configured."""
        return bool(
            self.PLIVO_AUTH_ID
            and self.PLIVO_AUTH_TOKEN
            and self.PLIVO_AUTH_ID.strip() != ""
            and self.PLIVO_AUTH_TOKEN.strip() != ""
        )

    EXOTEL_API_KEY: str | None = None
    EXOTEL_BUSINESS_API_KEYS: str | None = None  # Multi-tenant mapping: "key1:biz_id1,key2:biz_id2"
    EXOTEL_INTEGRATION_KEY: str | None = None
    EXOTEL_BUSINESS_ID: str | None = None
    EXOTEL_CALLER_ID: str | None = None

    @property
    def is_exotel_configured(self) -> bool:
        """Check whether Exotel API key or integration keys are configured."""
        return bool(self.EXOTEL_API_KEY or self.EXOTEL_INTEGRATION_KEY)

    # AI Conversational Voice Engine Settings (Phase 3)
    AI_PROVIDER: str = "mock"  # "mock", "openai", "gemini"
    AI_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OPENAI_API_KEY",
            "openai_api_key",
            "OPENAI_KEY",
            "openai_key",
            "OPEN_AI_KEY",
            "OPENAI_TTS_API_KEY",
        ),
    )
    GEMINI_API_KEY: str | None = None
    AI_TEMPERATURE: float = 0.2
    ENABLE_TANGLISH: bool = True

    # Tata Smartflo Cloud Telephony Settings (Phase 4)
    SMARTFLO_API_TOKEN: str | None = None
    SMARTFLO_CLICK2CALL_KEY: str | None = None
    SMARTFLO_BASE_URL: str = "https://api-smartflo.tatateleservices.com/v1"
    SMARTFLO_CALLER_ID: str | None = None
    SMARTFLO_WEBHOOK_TOKEN: str | None = None
    SMARTFLO_BUSINESS_MAPPING: str | None = None  # Format: "did1:biz_id1,did2:biz_id2"

    # Real-Time Voice Streaming, STT & TTS Settings (Phase 5)
    STT_PROVIDER: str = "whisper"  # "whisper", "deepgram", "mock"
    DEEPGRAM_API_KEY: str | None = None
    DEEPGRAM_MODEL: str = "nova-3"
    DEEPGRAM_LANGUAGE: str = "multi"
    TTS_PROVIDER: str = "openai"  # "openai", "elevenlabs", "mock", "carrier"
    ELEVENLABS_API_KEY: str | None = None
    ELEVENLABS_VOICE_ID: str = "EXAVITQu4vr4xnSDxMaL"  # Default premade multilingual voice (Sarah)
    ELEVENLABS_VOICE_ID_TA: str | None = None  # Optional dedicated voice override for Tamil
    ELEVENLABS_VOICE_ID_TE: str | None = None  # Optional dedicated voice override for Telugu
    ELEVENLABS_VOICE_ID_EN: str | None = None  # Optional dedicated voice override for English
    ELEVENLABS_MODEL_ID: str = "eleven_multilingual_v2"
    ENABLE_BARGE_IN: bool = True
    VAD_ENERGY_THRESHOLD: float = 400.0
    VAD_SILENCE_TIMEOUT_MS: int = 800
    STREAM_CHUNK_SIZE_BYTES: int = 160  # 20ms at 8000Hz 8-bit mu-law

    # Barge-In & Acoustic Echo Suppression Parameters
    BARGE_IN_GRACE_PERIOD_MS: int = 1200  # Suppress barge-in during initial 1.2s of playback to block acoustic echo
    BARGE_IN_MIN_SPEECH_FRAMES: int = 5  # Minimum consecutive speech frames (5 frames = 100ms)
    BARGE_IN_ENERGY_THRESHOLD: float = 850.0  # Elevated energy required to interrupt active assistant

    @property
    def is_smartflo_configured(self) -> bool:
        """Check whether essential Tata Smartflo credentials are configured."""
        return bool(
            self.SMARTFLO_API_TOKEN
            and self.SMARTFLO_API_TOKEN.strip() != ""
            and self.SMARTFLO_CALLER_ID
            and self.SMARTFLO_CALLER_ID.strip() != ""
        )

    def get_smartflo_did_map(self) -> dict[str, str]:
        """Return parsed dictionary mapping Smartflo DIDs to business tenant IDs."""
        mapping: dict[str, str] = {}
        if self.SMARTFLO_BUSINESS_MAPPING:
            for pair in self.SMARTFLO_BUSINESS_MAPPING.split(","):
                pair = pair.strip()
                if ":" in pair:
                    did, biz_id = pair.split(":", 1)
                    if did.strip() and biz_id.strip():
                        mapping[did.strip()] = biz_id.strip()
        return mapping

    @property
    def is_exotel_gateway_configured(self) -> bool:
        """Check whether Exotel body-payload gateway authentication is configured."""
        return bool(
            self.EXOTEL_INTEGRATION_KEY
            and self.EXOTEL_BUSINESS_ID
            and self.EXOTEL_INTEGRATION_KEY.strip() != ""
            and self.EXOTEL_BUSINESS_ID.strip() != ""
        )

    def get_exotel_key_map(self) -> dict[str, str]:
        """Return parsed dictionary mapping API keys to business tenant IDs."""
        mapping: dict[str, str] = {}
        if self.EXOTEL_BUSINESS_API_KEYS:
            for pair in self.EXOTEL_BUSINESS_API_KEYS.split(","):
                pair = pair.strip()
                if ":" in pair:
                    k, b = pair.split(":", 1)
                    if k.strip() and b.strip():
                        mapping[k.strip()] = b.strip()
        return mapping

    @property
    def is_twilio_configured(self) -> bool:
        """Check whether essential Twilio credentials and phone number are configured."""
        return bool(
            self.TWILIO_ACCOUNT_SID
            and self.TWILIO_AUTH_TOKEN
            and self.TWILIO_PHONE_NUMBER
            and self.TWILIO_ACCOUNT_SID.strip() != ""
            and self.TWILIO_AUTH_TOKEN.strip() != ""
            and self.TWILIO_PHONE_NUMBER.strip() != ""
        )

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

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Enforce strong, non-default SECRET_KEY and bootstrap credentials in production environment."""
        if self.ENVIRONMENT.lower() == "production":
            insecure_keys = {
                "temporary_secret_key_change_in_production_environment",
                "generate-a-secure-random-secret-key-for-production",
                "secret",
                "changeme",
                "",
            }
            if self.SECRET_KEY in insecure_keys or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "Production environment requires a strong, cryptographically random SECRET_KEY "
                    "(at least 32 characters). Generate one with: openssl rand -hex 32"
                )

            # In production, default or weak superuser passwords are strictly rejected
            insecure_passwords = {"SuperAdmin@123", "Admin@123", "password", "password123", "admin123", "12345678"}
            if self.FIRST_SUPERUSER_PASSWORD:
                if self.FIRST_SUPERUSER_PASSWORD in insecure_passwords or len(self.FIRST_SUPERUSER_PASSWORD) < 12:
                    raise ValueError(
                        "Production environment requires FIRST_SUPERUSER_PASSWORD to be at least 12 characters "
                        "and not match default development passwords."
                    )
        return self

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Prioritize project .env file settings over global Windows/OS environment variables
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()


settings = get_settings()
