"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = BACKEND_ROOT / ".env"
DEFAULT_CONFIG_FILE = BACKEND_ROOT / "config.yaml"
DEFAULT_DATABASE_FILE = BACKEND_ROOT / "spotify_curator.db"


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
    secret_key: str = "change-me"
    frontend_url: str = "http://localhost:5173"
    database_url: str = f"sqlite:///{DEFAULT_DATABASE_FILE}"
    config_path: Path = DEFAULT_CONFIG_FILE

    spotify_scopes: str = (
        "user-read-recently-played user-top-read user-library-read "
        "playlist-read-private playlist-modify-private playlist-modify-public "
        "user-read-email user-read-private"
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
