"""Database setup and models."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, create_engine
from sqlalchemy.engine import Engine
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


class UserRecord(Base):
    """Spotify profile for the currently connected account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    spotify_id: Mapped[str] = mapped_column(String(64), default="")
    display_name: Mapped[str] = mapped_column(String(256), default="")
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    product: Mapped[str | None] = mapped_column(String(32), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
    spotify_playlist_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DiscoverRunRecord(Base):
    """Log of auto-discovery playlist runs."""

    __tablename__ = "discover_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playlist_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    playlist_name: Mapped[str] = mapped_column(String(256))
    tracks_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CleanupRunRecord(Base):
    """Log of cleanup operations."""

    __tablename__ = "cleanup_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playlist_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlaylistScanCacheRecord(Base):
    """Cached duplicate/unavailable stats for a playlist."""

    __tablename__ = "playlist_scan_cache"

    playlist_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scan_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlaylistListCacheRecord(Base):
    """Cached playlist list for offline / rate-limit fallback."""

    __tablename__ = "playlist_list_cache"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    playlists_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SpotifyUsageRecord(Base):
    """Rolling Spotify API usage and rate-limit backoff."""

    __tablename__ = "spotify_usage"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    request_timestamps_json: Mapped[str] = mapped_column(Text, default="[]")
    rate_limited_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AdvisorPresetRecord(Base):
    """User-saved AI advisor scan presets."""

    __tablename__ = "advisor_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    options_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AdvisorScheduleRecord(Base):
    """Singleton AI advisor schedule configuration."""

    __tablename__ = "advisor_schedule"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(default=False)
    cron: Mapped[str] = mapped_column(String(64), default="0 9 * * 0")
    options_json: Mapped[str] = mapped_column(Text)
    notify_email: Mapped[bool] = mapped_column(default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_run_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_run_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AdvisorScheduleRunRecord(Base):
    """History entry for scheduled advisor runs."""

    __tablename__ = "advisor_schedule_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(32), default="schedule")


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create database tables."""
    Base.metadata.create_all(bind=engine)
    _migrate_discover_runs(engine)
    _migrate_curate_sessions(engine)


def _migrate_curate_sessions(db_engine: Engine) -> None:
    """Add curate_sessions.spotify_playlist_id for existing SQLite databases."""
    from sqlalchemy import inspect, text

    inspector = inspect(db_engine)
    if "curate_sessions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("curate_sessions")}
    if "spotify_playlist_id" in columns:
        return
    with db_engine.connect() as conn:
        conn.execute(
            text(
                "ALTER TABLE curate_sessions ADD COLUMN spotify_playlist_id VARCHAR(64)"
            ),
        )
        conn.commit()


def _migrate_discover_runs(db_engine: Engine) -> None:
    """Add discover_runs.status for existing SQLite databases."""
    from sqlalchemy import inspect, text

    inspector = inspect(db_engine)
    if "discover_runs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("discover_runs")}
    if "status" in columns:
        return
    with db_engine.connect() as conn:
        conn.execute(
            text(
                "ALTER TABLE discover_runs "
                "ADD COLUMN status VARCHAR(32) DEFAULT 'pending' NOT NULL",
            ),
        )
        conn.execute(
            text(
                "UPDATE discover_runs "
                "SET status = 'saved' "
                "WHERE playlist_id IS NOT NULL AND playlist_id != ''",
            ),
        )
        conn.commit()


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
