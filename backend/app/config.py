"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "https://127.0.0.1:8000/auth/callback"
    secret_key: str = "change-me"
    frontend_url: str = "http://localhost:5173"
    database_url: str = "sqlite:///./spotify_curator.db"
    config_path: Path = Path("config.yaml")

    spotify_scopes: str = (
        "user-read-recently-played user-top-read user-library-read "
        "playlist-read-private playlist-modify-private playlist-modify-public "
        "user-read-email user-read-private"
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
