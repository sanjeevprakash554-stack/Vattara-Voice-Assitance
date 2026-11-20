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

    # AI Conversational Voice Engine Settings (Phase 3)
    AI_PROVIDER: str = "gemini"  # "gemini", "openai", "mock"
    AI_MODEL: str = "gemini-3.1-flash-lite"
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
    GEMINI_API_KEY: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GEMINI_API_KEY",
            "gemini_api_key",
            "GOOGLE_API_KEY",
            "google_api_key",
        ),
    )
    AI_TEMPERATURE: float = 0.2
    ENABLE_TANGLISH: bool = True

    # Real-Time Voice Streaming, STT & TTS Settings (Phase 5)
    STT_PROVIDER: str = "sarvam"  # "sarvam", "deepgram", "whisper", "mock"
    SARVAM_STT_MODEL: str = "saaras:v4"
    SARVAM_STT_LANGUAGE: str = "auto"
    SARVAM_STT_ENCODING: str = "mulaw"
    SARVAM_STT_SAMPLE_RATE: int = 8000
    DEEPGRAM_API_KEY: str | None = None
    DEEPGRAM_MODEL: str = "nova-3"
    DEEPGRAM_LANGUAGE: str = "multi"  # Deepgram Nova-3 multilingual mode supporting dynamic code-switching
    DEEPGRAM_LANGUAGE_HINTS: str = "ta,en"  # Biasing hints for Tamil and English telephony

    @property
    def deepgram_language_hints_list(self) -> list[str]:
        """Return parsed list of language hints for Deepgram Nova-3 multilingual mode."""
        if not self.DEEPGRAM_LANGUAGE_HINTS:
            return ["ta", "en"]
        hints = [h.strip() for h in self.DEEPGRAM_LANGUAGE_HINTS.split(",") if h.strip()]
        return hints or ["ta", "en"]
    TTS_PROVIDER: str = "sarvam"  # "sarvam", "elevenlabs", "openai", "mock", "carrier"
    SARVAM_API_KEY: str | None = None
    SARVAM_TTS_MODEL: str = "bulbul:v4-flash"
    SARVAM_VOICE_ID: str = "gokul_ta_narration"  # Default Sarvam Bulbul v4 Flash voice ID
    SARVAM_TAMIL_SPEAKER: str = "gokul_ta_narration"
    SARVAM_ENGLISH_SPEAKER: str = "shubh_en_narration_gentle"
    SARVAM_TELUGU_SPEAKER: str = "tarun_te_narration"
    SARVAM_TTS_PACE: float = 1.0
    SARVAM_TTS_ENABLE_PREPROCESSING: bool = True
    SARVAM_TTS_TIMEOUT: float = 8.0
    ELEVENLABS_API_KEY: str | None = None
    ELEVENLABS_VOICE_ID: str = "EXAVITQu4vr4xnSDxMaL"  # Default premade multilingual voice (Sarah)
    ELEVENLABS_VOICE_ID_TA: str | None = None  # Optional dedicated voice override for Tamil
    ELEVENLABS_VOICE_ID_TE: str | None = None  # Optional dedicated voice override for Telugu
    ELEVENLABS_VOICE_ID_EN: str | None = None  # Optional dedicated voice override for English
    ELEVENLABS_MODEL_ID: str = "eleven_multilingual_v2"
    ENABLE_BARGE_IN: bool = True

    # Real-Time Voice Activity Detection (VAD) & Noise Suppression
    VAD_MODE: int = 2  # WebRTC VAD aggressiveness: 0 (normal), 1 (low bitrate), 2 (aggressive), 3 (very aggressive)
    VAD_ECHO_MODE: int = 3  # Aggressiveness mode during assistant playback or echo tail
    VAD_ENERGY_THRESHOLD: float = 350.0  # Base energy threshold (RMS amplitude)
    VAD_SILENCE_TIMEOUT_MS: int = 600  # Silence duration to trigger endpoint detection (preserves natural sentence pauses)
    VAD_SPEECH_ONSET_FRAMES: int = 5  # Consecutive speech frames required to trigger speech onset (5 frames = 100ms)
    VAD_ADAPTIVE_SNR_MARGIN: float = 160.0  # Required RMS energy margin above running noise floor (rejects fans/traffic)
    VAD_NOISE_FLOOR_ALPHA: float = 0.05  # EMA smoothing factor for background noise floor estimation
    VAD_MAX_ZCR: float = 0.42  # Maximum Zero-Crossing Rate for voiced speech frames (rejects high-freq hiss)
    STREAM_CHUNK_SIZE_BYTES: int = 160  # 20ms at 8000Hz 8-bit mu-law
    MAX_SPEECH_BUFFER_BYTES: int = 96000  # Safe cap: 6.0 seconds of audio at 8kHz 16-bit linear PCM (16,000 B/s)

    # Silence & Inactivity Management (Prevents premature call termination)
    CALLER_INACTIVITY_PROMPT_1_SEC: float = 18.0  # Polite check after 18s of caller silence
    CALLER_INACTIVITY_PROMPT_2_SEC: float = 45.0  # Second polite prompt after 45s of silence
    CALLER_MAX_INACTIVITY_SEC: float = 180.0  # Maximum caller silence duration before polite conclusion (3 minutes)
    WS_HEARTBEAT_INTERVAL_SEC: float = 15.0  # WebSocket ping/pong interval to prevent 60-90s edge proxy timeouts

    # Multilingual Telephone Greeting Templates
    DEFAULT_GREETING_MODE: str = "bilingual"  # "bilingual", "tamil", "english", "auto"
    GREETING_TEMPLATE_BILINGUAL: str = "வணக்கம்! Welcome to {business_name}. How can I help you today?"
    GREETING_TEMPLATE_TAMIL: str = "வணக்கம்! {business_name}. உங்களுக்கு எப்படி உதவலாம்?"
    GREETING_TEMPLATE_ENGLISH: str = "Hello! Thank you for calling {business_name}. How may I help you?"
    GREETING_TEMPLATE_TANGLISH: str = "Vanakkam! {business_name}. Ungalukku eppadi udhavalam?"
    GREETING_TEMPLATE_TELUGU: str = "నమస్కారం! {business_name} కు స్వాగతం. నేను మీకు ఎలా సహాయపడగలను?"
    GREETING_TEMPLATE_TELUGLISH: str = "Namaskaram! {business_name}-ku swagatham. Nenu meeku ela sahayapadagalanu?"

    # Barge-In & Acoustic Echo Suppression Parameters
    BARGE_IN_GRACE_PERIOD_MS: int = 2000  # Suppress barge-in during initial 2000ms of playback to block acoustic onset reflection
    BARGE_IN_MIN_SPEECH_FRAMES: int = 10  # Minimum consecutive speech frames (10 frames = 200ms) to reject noise clicks
    BARGE_IN_ENERGY_THRESHOLD: float = 1200.0  # Elevated energy required to interrupt active assistant (rejects echo and room noise)
    ECHO_SETTLING_WINDOW_MS: int = 500  # Tail window after playback to reject acoustic echo reflections

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Return explicit database URL if set; otherwise construct PostgreSQL URL from credentials."""
        if self.SQLALCHEMY_DATABASE_URI:
            uri = self.SQLALCHEMY_DATABASE_URI
            if uri.startswith("sqlite:///") and not uri.startswith("sqlite:////"):
                import os
                # Ensure relative SQLite path reliably points to backend/vattara.db regardless of process launch cwd
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                backend_db = os.path.join(base_dir, "vattara.db").replace("\\", "/")
                if os.path.exists(backend_db):
                    return f"sqlite:///{backend_db}"
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
