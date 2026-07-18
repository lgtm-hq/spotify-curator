"""Track Spotify API usage and rate-limit state for UI feedback."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from spotipy.exceptions import SpotifyException
from sqlalchemy.orm import Session

from app.db import SpotifyUsageRecord, ensure_utc, utcnow

WINDOW_SECONDS = 30
# Conservative estimate for dev-mode rolling window; exact caps unpublished.
ESTIMATED_LIMIT = 100
WARNING_THRESHOLD = 0.7


def _get_record(db: Session) -> SpotifyUsageRecord:
    record = db.get(SpotifyUsageRecord, 1)
    if record is None:
        record = SpotifyUsageRecord(id=1, request_timestamps_json="[]")
        db.add(record)
        db.commit()
    return cast(SpotifyUsageRecord, record)


def _load_timestamps(record: SpotifyUsageRecord) -> list[datetime]:
    try:
        raw = json.loads(record.request_timestamps_json or "[]")
    except json.JSONDecodeError:
        return []
    timestamps: list[datetime] = []
    for item in raw:
        if isinstance(item, str):
            timestamps.append(datetime.fromisoformat(item))
    return timestamps


def _save_timestamps(
    db: Session, record: SpotifyUsageRecord, timestamps: list[datetime]
) -> None:
    record.request_timestamps_json = json.dumps(
        [ts.astimezone(UTC).isoformat() for ts in timestamps],
    )
    db.commit()


def record_spotify_request(db: Session, *, count: int = 1) -> None:
    """Record one or more Spotify API requests in the rolling window."""
    record = _get_record(db)
    now = utcnow()
    cutoff = now - timedelta(seconds=WINDOW_SECONDS)
    timestamps = [ts for ts in _load_timestamps(record) if ensure_utc(ts) >= cutoff]
    for _ in range(max(count, 1)):
        timestamps.append(now)
    _save_timestamps(db, record, timestamps)


def record_rate_limit(db: Session, *, retry_after_seconds: int | None) -> None:
    """Persist rate-limit backoff from a 429 response."""
    record = _get_record(db)
    seconds = (
        retry_after_seconds if retry_after_seconds and retry_after_seconds > 0 else 60
    )
    record.rate_limited_until = utcnow() + timedelta(seconds=seconds)
    db.commit()


def retry_after_from_exception(exc: SpotifyException) -> int | None:
    """Parse Retry-After header from a Spotipy exception."""
    headers = getattr(exc, "headers", None) or {}
    raw = headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def usage_status(
    db: Session,
    *,
    last_fetched_at: datetime | None = None,
) -> dict[str, Any]:
    """Return Spotify usage snapshot for the dashboard."""
    record = _get_record(db)
    now = utcnow()
    cutoff = now - timedelta(seconds=WINDOW_SECONDS)
    timestamps = [ts for ts in _load_timestamps(record) if ensure_utc(ts) >= cutoff]
    requests_in_window = len(timestamps)
    usage_ratio = min(requests_in_window / ESTIMATED_LIMIT, 1.0)
    usage_percent = int(round(usage_ratio * 100))

    limited_until = (
        ensure_utc(record.rate_limited_until)
        if record.rate_limited_until is not None
        else None
    )
    seconds_until_reset: int | None = None
    if limited_until and limited_until > now:
        seconds_until_reset = max(0, int((limited_until - now).total_seconds()))

    state: Literal["ok", "warning", "limited"]
    if seconds_until_reset is not None and seconds_until_reset > 0:
        state = "limited"
    elif usage_ratio >= WARNING_THRESHOLD:
        state = "warning"
    else:
        state = "ok"

    return {
        "state": state,
        "requests_in_window": requests_in_window,
        "window_seconds": WINDOW_SECONDS,
        "estimated_limit": ESTIMATED_LIMIT,
        "usage_percent": usage_percent,
        "rate_limited_until": limited_until.isoformat() if limited_until else None,
        "seconds_until_reset": seconds_until_reset,
        "last_fetched_at": last_fetched_at.isoformat() if last_fetched_at else None,
    }
