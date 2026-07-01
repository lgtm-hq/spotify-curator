"""Database setup and models."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class TokenRecord(Base):
    """Stored Spotify OAuth tokens for the single user."""

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str] = mapped_column(String(512), default="")


class TasteProfileRecord(Base):
    """Cached taste profile JSON."""

    __tablename__ = "taste_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    profile_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CurateSessionRecord(Base):
    """Mood concierge interview session."""

    __tablename__ = "curate_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_json: Mapped[str] = mapped_column(Text, default="[]")
    playlist_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_tracks_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DiscoverRunRecord(Base):
    """Log of auto-discovery playlist runs."""

    __tablename__ = "discover_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playlist_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    playlist_name: Mapped[str] = mapped_column(String(256))
    tracks_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CleanupRunRecord(Base):
    """Log of cleanup operations."""

    __tablename__ = "cleanup_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playlist_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create database tables."""
    Base.metadata.create_all(bind=engine)


def utcnow() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize datetimes loaded from SQLite to UTC-aware."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def dumps_json(data: object) -> str:
    """Serialize data to JSON string."""
    return json.dumps(data, default=str)


def loads_json(text: str) -> object:
    """Deserialize JSON string."""
    return json.loads(text)
