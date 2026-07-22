"""SaaS-specific settings (API / worker). Bot keeps using config.settings."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _ROOT / ".env"


class SaasSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres in Docker; sqlite fallback for local smoke tests without Docker
    SAAS_DATABASE_URL: str = "sqlite+aiosqlite:///./saas_ninavpn.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "change-me-in-production-use-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    API_CORS_ORIGINS: str = "*"
    API_RATE_LIMIT: str = "60/minute"
    AUTH_RATE_LIMIT: str = "20/minute"

    # Payment return URLs (Expo / web)
    SAAS_PUBLIC_BASE_URL: Optional[str] = None
    SAAS_SUCCESS_PATH: str = "/pay/success"
    SAAS_FAIL_PATH: str = "/pay/fail"

    # Mock gateway when T-Bank not configured
    PAYMENT_MOCK_ENABLED: bool = True

    BOT_TOKEN: Optional[str] = None
    ADMIN_ID: Optional[int] = None
    ADMIN_IDS: Optional[str] = None
    # Comma-separated emails promoted to admin on login/me
    ADMIN_EMAILS: str = ""

    # OAuth — Google ID token audiences (comma-separated client IDs)
    GOOGLE_CLIENT_IDS: str = ""
    # Telegram Login Widget: max age of auth_date (seconds)
    TELEGRAM_AUTH_MAX_AGE_SEC: int = 86400
    TELEGRAM_BOT_USERNAME: Optional[str] = None

    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None

    # Panel user key offset for pure email users (avoid clash with real tg ids)
    PANEL_USER_KEY_BASE: int = 8_000_000_000_000


saas_settings = SaasSettings()
