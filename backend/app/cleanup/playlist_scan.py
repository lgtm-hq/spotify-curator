"""Efficient full-playlist scanning for cleanup suggestions."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import spotipy
from sqlalchemy.orm import Session

from app.cleanup.service import find_duplicates, find_unavailable
from app.db import PlaylistScanCacheRecord, dumps_json, ensure_utc, loads_json, utcnow
from app.playlists.models import PlaylistSummary, TrackArtist, TrackSummary
from app.playlists.service import list_playlists
from app.spotify_client import playlist_entry_track

logger = logging.getLogger(__name__)

PAGE_SIZE = 100
MAX_SCANNED_PLAYLISTS = 15
PARALLEL_SCAN_WORKERS = 4
SCAN_CACHE_TTL = timedelta(hours=1)

PageProgressCallback = Callable[[int], None]


@dataclass(frozen=True)
class PlaylistScanStats:
    """Aggregated cleanup stats for one playlist."""

    playlist_id: str
    playlist_name: str
    track_count: int
    tracks_scanned: int
    duplicate_tracks: int
    unavailable_tracks: int
    owned: bool
    full_scan: bool
    from_cache: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "playlist_id": self.playlist_id,
            "playlist_name": self.playlist_name,
            "track_count": self.track_count,
            "tracks_scanned": self.tracks_scanned,
            "duplicate_tracks": self.duplicate_tracks,
            "unavailable_tracks": self.unavailable_tracks,
            "owned": self.owned,
            "full_scan": self.full_scan,
            "from_cache": self.from_cache,
        }


def _minimal_track(entry: dict[str, Any]) -> TrackSummary | None:
    """Map a playlist item to a minimal track for duplicate/unavailable checks."""
    raw = playlist_entry_track(entry)
    if not raw or not raw.get("id"):
        return None
    artists = [
        TrackArtist(id=a.get("id"), name=str(a.get("name") or "Unknown"))
        for a in raw.get("artists", [])
    ]
    return TrackSummary(
        id=str(raw["id"]),
        name=str(raw.get("name") or "Unknown"),
        artists=artists,
        uri=str(raw.get("uri") or f"spotify:track:{raw['id']}"),
        is_playable=raw.get("is_playable") is not False,
    )


def _stats_from_tracks(
    *,
    playlist: PlaylistSummary,
    tracks: list[TrackSummary],
    from_cache: bool = False,
) -> PlaylistScanStats:
    duplicate_ids: set[str] = set()
    for issue in find_duplicates(tracks):
        duplicate_ids.update(issue.track_ids)

    unavailable_ids: set[str] = set()
    for issue in find_unavailable(tracks):
        unavailable_ids.update(issue.track_ids)

    return PlaylistScanStats(
        playlist_id=playlist.id,
        playlist_name=playlist.name,
        track_count=playlist.track_count or len(tracks),
        tracks_scanned=len(tracks),
        duplicate_tracks=len(duplicate_ids),
        unavailable_tracks=len(unavailable_ids),
        owned=playlist.can_edit,
        full_scan=True,
        from_cache=from_cache,
    )


def _metadata_stats(playlist: PlaylistSummary) -> PlaylistScanStats:
    return PlaylistScanStats(
        playlist_id=playlist.id,
        playlist_name=playlist.name,
        track_count=playlist.track_count,
        tracks_scanned=0,
        duplicate_tracks=0,
        unavailable_tracks=0,
        owned=playlist.can_edit,
        full_scan=False,
        from_cache=False,
    )


def _load_cached_stats(db: Session, *, playlist_id: str) -> PlaylistScanStats | None:
    record = db.get(PlaylistScanCacheRecord, playlist_id)
    if record is None:
        return None
    age = utcnow() - ensure_utc(record.updated_at)
    if age > SCAN_CACHE_TTL:
        return None
    data = loads_json(record.scan_json)
    if not isinstance(data, dict):
        return None
    return PlaylistScanStats(
        playlist_id=str(data["playlist_id"]),
        playlist_name=str(data["playlist_name"]),
        track_count=int(data.get("track_count") or 0),
        tracks_scanned=int(data.get("tracks_scanned") or 0),
        duplicate_tracks=int(data.get("duplicate_tracks") or 0),
        unavailable_tracks=int(data.get("unavailable_tracks") or 0),
        owned=bool(data.get("owned")),
        full_scan=bool(data.get("full_scan")),
        from_cache=True,
    )


def _save_cached_stats(db: Session, stats: PlaylistScanStats) -> None:
    record = db.get(PlaylistScanCacheRecord, stats.playlist_id)
    if record is None:
        record = PlaylistScanCacheRecord(playlist_id=stats.playlist_id)
        db.add(record)
    record.scan_json = dumps_json(stats.to_dict())
    record.updated_at = utcnow()
    db.commit()


def scan_playlist_full(
    sp: spotipy.Spotify,
    db: Session,
    *,
    playlist: PlaylistSummary,
    on_page: PageProgressCallback | None = None,
    use_cache: bool = True,
) -> PlaylistScanStats:
    """Scan every track in a playlist, paginating efficiently."""
    if playlist.track_count == 0:
        return _metadata_stats(playlist)

    if not playlist.can_edit:
        return _metadata_stats(playlist)

    if use_cache:
        cached = _load_cached_stats(db, playlist_id=playlist.id)
        if cached is not None:
            if on_page is not None:
                on_page(cached.tracks_scanned)
            return cached

    tracks: list[TrackSummary] = []
    offset = 0
    while True:
        page = sp.playlist_items(
            playlist.id,
            limit=PAGE_SIZE,
            offset=offset,
            additional_types=["track"],
        )
        items = page.get("items", [])
        for entry in items:
            track = _minimal_track(entry)
            if track:
                tracks.append(track)
        if on_page is not None:
            on_page(len(tracks))
        if not page.get("next"):
            break
        offset += PAGE_SIZE

    stats = _stats_from_tracks(playlist=playlist, tracks=tracks)
    _save_cached_stats(db, stats)
    return stats


def scan_playlists_parallel(
    *,
    access_token: str,
    db_factory: Callable[[], Session],
    playlists: list[PlaylistSummary],
    max_workers: int = PARALLEL_SCAN_WORKERS,
    on_playlist_start: Callable[[int, int, str, int], None] | None = None,
    on_playlist_page: Callable[[int, int], None] | None = None,
    on_playlist_done: Callable[[int, PlaylistScanStats], None] | None = None,
) -> list[PlaylistScanStats]:
    """Scan multiple owned playlists in parallel; metadata-only for others."""
    if not playlists:
        return []

    results: list[PlaylistScanStats | None] = [None] * len(playlists)

    def scan_at(index: int, playlist: PlaylistSummary) -> tuple[int, PlaylistScanStats]:
        if on_playlist_start is not None:
            on_playlist_start(
                index + 1,
                len(playlists),
                playlist.name,
                playlist.track_count,
            )

        if not playlist.can_edit or playlist.track_count == 0:
            stats = _metadata_stats(playlist)
            if on_playlist_done is not None:
                on_playlist_done(index, stats)
            return index, stats

        sp = spotipy.Spotify(auth=access_token)
        db = db_factory()
        try:
            def page_cb(loaded: int) -> None:
                if on_playlist_page is not None:
                    on_playlist_page(index, loaded)

            stats = scan_playlist_full(
                sp,
                db,
                playlist=playlist,
                on_page=page_cb,
            )
        finally:
            db.close()

        if on_playlist_done is not None:
            on_playlist_done(index, stats)
        return index, stats

    worker_count = min(max_workers, len(playlists))
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [
            pool.submit(scan_at, index, playlist)
            for index, playlist in enumerate(playlists)
        ]
        for future in as_completed(futures):
            index, stats = future.result()
            results[index] = stats

    return [stats for stats in results if stats is not None]


def select_playlists_to_scan(
    sp: spotipy.Spotify,
    *,
    current_user_id: str | None,
) -> tuple[list[PlaylistSummary], list[PlaylistSummary]]:
    """Return playlists selected for scan and the full library list."""
    playlists = list_playlists(sp, current_user_id=current_user_id)
    ranked = sorted(
        [playlist for playlist in playlists if playlist.track_count > 0],
        key=lambda item: item.track_count,
        reverse=True,
    )
    return ranked[:MAX_SCANNED_PLAYLISTS], playlists
