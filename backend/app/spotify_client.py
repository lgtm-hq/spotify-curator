"""Spotify API client wrapper."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar, cast

import httpx
import requests
import spotipy
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.spotify_oauth import SPOTIFY_TOKEN_ENDPOINT, refresh_access_token
from app.config import get_settings
from app.db import TokenRecord, ensure_utc

T = TypeVar("T")

TOKEN_REFRESH_BUFFER = timedelta(minutes=1)


def create_spotify_client(access_token: str) -> spotipy.Spotify:
    """Return Spotipy client that fails fast instead of long 429 backoff sleeps."""
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=0)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return spotipy.Spotify(
        auth=access_token,
        requests_timeout=15,
        requests_session=session,
    )


async def call_spotify[T](fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run blocking Spotipy work off the asyncio event loop."""
    return await asyncio.to_thread(fn, *args, **kwargs)


def refresh_access_token_sync(*, refresh_token: str) -> dict[str, object]:
    """Refresh an expired access token without asyncio."""
    settings = get_settings()
    response = httpx.post(
        SPOTIFY_TOKEN_ENDPOINT,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.spotify_client_id,
            "client_secret": settings.spotify_client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    return payload


def _token_needs_refresh(expires_at: datetime) -> bool:
    """Return True when the access token should be refreshed."""
    return ensure_utc(expires_at) <= datetime.now(UTC) + TOKEN_REFRESH_BUFFER


def _load_token_record(db: Session) -> TokenRecord:
    record = db.get(TokenRecord, 1)
    if record is None:
        raise HTTPException(status_code=401, detail="Spotify not connected")
    return cast(TokenRecord, record)


def _refresh_token_record(db: Session, record: TokenRecord) -> TokenRecord:
    """Refresh and persist a Spotify token record."""
    if not record.refresh_token:
        raise HTTPException(status_code=401, detail="Spotify token expired")
    token_data = refresh_access_token_sync(refresh_token=record.refresh_token)
    record.access_token = str(token_data["access_token"])
    expires_in = token_data.get("expires_in", 3600)
    if not isinstance(expires_in, (int, float)):
        expires_in = 3600
    record.expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))
    refresh = token_data.get("refresh_token")
    if refresh:
        record.refresh_token = str(refresh)
    db.commit()
    return record


def _ensure_fresh_token_record(db: Session) -> TokenRecord:
    """Refresh the stored Spotify token when it is near expiry."""
    record = _load_token_record(db)
    if _token_needs_refresh(record.expires_at):
        record = _refresh_token_record(db, record)
    return record


class SpotifyJobAuth:
    """Thread-safe token cache for long-running background jobs.

    Checks the stored ``expires_at`` before calling Spotify. Workers share one
    instance so refresh happens at most once when the token actually expires.
    """

    def __init__(self, db_factory: Callable[[], Session]) -> None:
        """Initialize the cache with a session factory for token refreshes."""
        self._db_factory = db_factory
        self._lock = threading.Lock()
        self._access_token: str | None = None
        self._expires_at: datetime | None = None

    def invalidate(self) -> None:
        """Drop cached credentials after a 401 so the next call re-reads/refreshes."""
        with self._lock:
            self._access_token = None
            self._expires_at = None

    def _cache(self, record: TokenRecord) -> str:
        self._access_token = record.access_token
        self._expires_at = ensure_utc(record.expires_at)
        return self._access_token

    def access_token(self, db: Session) -> str:
        """Return a valid access token, refreshing only when expired."""
        with self._lock:
            if (
                self._access_token is not None
                and self._expires_at is not None
                and not _token_needs_refresh(self._expires_at)
            ):
                return self._access_token

            record = _load_token_record(db)
            if not _token_needs_refresh(record.expires_at):
                return self._cache(record)

            return self._cache(_refresh_token_record(db, record))

    def client(self, db: Session) -> spotipy.Spotify:
        """Return an authenticated Spotipy client for the current token."""
        return create_spotify_client(self.access_token(db))


def get_spotify_client_sync(db: Session) -> spotipy.Spotify:
    """Return an authenticated Spotipy client for background jobs."""
    record = _ensure_fresh_token_record(db)
    return create_spotify_client(record.access_token)


async def get_spotify_client(db: Session) -> spotipy.Spotify:
    """Return an authenticated Spotipy client, refreshing tokens if needed."""
    record = _load_token_record(db)
    if _token_needs_refresh(record.expires_at):
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

    return create_spotify_client(record.access_token)


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


def paginate_playlist_items(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Paginate playlist track items."""
    return paginate(
        sp,
        "playlist_items",
        playlist_id=playlist_id,
        limit=limit,
        additional_types=["track"],
    )


def paginate_playlist_items_lite(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
    max_items: int = 100,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch up to max_items playlist entries without loading the full playlist."""
    method = sp.playlist_items
    results: list[dict[str, Any]] = []
    offset = 0
    while len(results) < max_items:
        page = method(
            playlist_id,
            limit=min(limit, max_items - len(results)),
            offset=offset,
            additional_types=["track"],
        )
        items = page.get("items", [])
        if not items:
            break
        results.extend(items)
        if not page.get("next"):
            break
        offset += limit
    return results[:max_items]
