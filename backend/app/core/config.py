"""
core/config.py
--------------
Reads environment variables (from .env or the shell) and exposes them
as a typed Settings object used throughout the application.
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "dev-secret-key-change-in-production"
    APP_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./patientcase.db"

    # ── LLM & AI Clinical Insights ───────────────────────────────────────
    LLM_PROVIDER: str = "hosted"  # "hosted" | "local" | "mock"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_EXTRACTION_MODEL: str = "claude-haiku-5-5"
    ANTHROPIC_REASONING_MODEL: str = "claude-sonnet-5-5"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434/v1"
    OLLAMA_MODEL: str = "llama3.2:3b"
    AI_FOLLOWUPS_ENABLED: bool = False
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_MAX_RETRIES: int = 3
    LLM_MAX_TOKENS: int = 4096

    # ── CORS ─────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # ── File uploads ──────────────────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 20

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
