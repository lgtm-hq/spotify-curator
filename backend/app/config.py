"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = BACKEND_ROOT / ".env"
DEFAULT_CONFIG_FILE = BACKEND_ROOT / "config.yaml"
DEFAULT_DATABASE_FILE = BACKEND_ROOT / "spotify_curator.db"
PLACEHOLDER_SECRET_KEYS = {
    "change-me",
    "change-me-to-a-random-string",
}


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "https://127.0.0.1:8000/auth/callback"
    secret_key: str = Field(default="", min_length=32, validate_default=True)
    frontend_url: str = "http://127.0.0.1:5173"
    database_url: str = f"sqlite:///{DEFAULT_DATABASE_FILE}"
    config_path: Path = DEFAULT_CONFIG_FILE

    spotify_scopes: str = (
        "user-read-recently-played user-top-read user-library-read "
        "playlist-read-private playlist-modify-private playlist-modify-public "
        "user-read-email user-read-private"
    )

    @field_validator("secret_key", mode="before")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        """Require deployment-specific session signing keys."""
        secret_key = value.strip()
        if secret_key.casefold() in PLACEHOLDER_SECRET_KEYS:
            msg = "SECRET_KEY must be replaced with a deployment-specific value"
            raise ValueError(msg)
        return secret_key


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
