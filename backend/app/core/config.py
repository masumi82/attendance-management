from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_ENV: Literal["development", "production", "test"] = "development"
    TZ: str = "Asia/Tokyo"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = Field(..., description="SQLAlchemy database URL")

    JWT_SECRET: str = Field(..., min_length=16)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRES_DAYS: int = 14
    # Optional pepper for refresh-token hashing. When set, adds an
    # application-wide secret to the SHA-256 input so a leaked DB alone
    # cannot be used to recognize a stolen token.
    REFRESH_TOKEN_PEPPER: str = ""

    # Argon2id parameters (defaults tuned for Raspberry Pi 4).
    # See https://argon2-cffi.readthedocs.io/en/stable/parameters.html
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST_KB: int = 65536  # 64 MiB
    ARGON2_PARALLELISM: int = 2

    # Rate limits (per client IP).
    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_REFRESH: str = "30/minute"

    CORS_ORIGINS: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@example.local"
    SMTP_USE_TLS: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
