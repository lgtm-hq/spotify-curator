"""Spotify API client wrapper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import spotipy
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.spotify_oauth import refresh_access_token
from app.db import TokenRecord, ensure_utc


async def get_spotify_client(db: Session) -> spotipy.Spotify:
    """Return an authenticated Spotipy client, refreshing tokens if needed."""
    record = db.get(TokenRecord, 1)
    if record is None:
        raise HTTPException(status_code=401, detail="Spotify not connected")

    expires_at = ensure_utc(record.expires_at)
    if expires_at <= datetime.now(UTC) + timedelta(minutes=1):
        if not record.refresh_token:
            raise HTTPException(status_code=401, detail="Spotify token expired")
        token_data = await refresh_access_token(refresh_token=record.refresh_token)
        record.access_token = str(token_data["access_token"])
        expires_in = token_data.get("expires_in", 3600)
        if not isinstance(expires_in, (int, float)):
            expires_in = 3600
        record.expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))
        refresh = token_data.get("refresh_token")
        if refresh:
            record.refresh_token = str(refresh)
        db.commit()

    return spotipy.Spotify(auth=record.access_token)


def playlist_track_total(playlist: dict[str, Any]) -> int:
    """Return playlist track count from Spotify items/tracks metadata."""
    container = playlist.get("items") or playlist.get("tracks") or {}
    total = container.get("total")
    return int(total) if total is not None else 0


def playlist_entry_track(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Extract a track object from a playlist page entry."""
    track = entry.get("item") or entry.get("track")
    if not isinstance(track, dict):
        return None
    if track.get("type") != "track" or not track.get("id"):
        return None
    return track


def paginate(
    sp: spotipy.Spotify,
    method_name: str,
    **kwargs: object,
) -> list[dict[str, Any]]:
    """Paginate through Spotify API results."""
    method = getattr(sp, method_name)
    results: list[dict[str, Any]] = []
    offset = 0
    limit_raw = kwargs.pop("limit", 50)
    limit = int(limit_raw) if isinstance(limit_raw, (int, float, str)) else 50
    while True:
        page = method(limit=limit, offset=offset, **kwargs)
        items = page.get("items", [])
        results.extend(items)
        if not page.get("next"):
            break
        offset += limit
    return results
