"""Map Spotify playlist IDs to app-generated (curated) sources."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db import CurateSessionRecord, DiscoverRunRecord


def curated_playlist_sources(db: Session) -> dict[str, dict[str, Any]]:
    """Return playlist IDs created by Discover or Mood Concierge."""
    sources: dict[str, dict[str, Any]] = {}

    discover_runs = (
        db.query(DiscoverRunRecord)
        .filter(DiscoverRunRecord.playlist_id.isnot(None))
        .order_by(DiscoverRunRecord.created_at.desc())
        .all()
    )
    for run in discover_runs:
        playlist_id = run.playlist_id
        if not playlist_id or playlist_id in sources:
            continue
        sources[playlist_id] = {
            "source": "discover",
            "label": "Discover",
            "created_at": run.created_at.isoformat(),
        }

    curate_sessions = (
        db.query(CurateSessionRecord)
        .filter(CurateSessionRecord.spotify_playlist_id.isnot(None))
        .order_by(CurateSessionRecord.updated_at.desc())
        .all()
    )
    for session in curate_sessions:
        playlist_id = session.spotify_playlist_id
        if not playlist_id or playlist_id in sources:
            continue
        sources[playlist_id] = {
            "source": "curate",
            "label": "Curate",
            "created_at": session.updated_at.isoformat(),
        }

    return sources
