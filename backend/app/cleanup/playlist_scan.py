"""Efficient full-playlist scanning for cleanup suggestions."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import spotipy
from spotipy.exceptions import SpotifyException
from sqlalchemy.orm import Session

from app.cleanup.service import find_duplicates, find_unavailable
from app.cleanup.suggest_options import ALL_FOCUS_AREAS, CleanupSuggestOptions
from app.db import PlaylistScanCacheRecord, dumps_json, ensure_utc, loads_json, utcnow
from app.playlists.models import PlaylistSummary, TrackArtist, TrackSummary
from app.playlists.service import list_playlists
from app.spotify_client import SpotifyJobAuth, playlist_entry_track
from app.spotify_usage import record_rate_limit, retry_after_from_exception

logger = logging.getLogger(__name__)

PAGE_SIZE = 100
PARALLEL_SCAN_WORKERS = 4
CONSERVATIVE_SCAN_WORKERS = 2
SCAN_CACHE_TTL = timedelta(hours=1)
SCAN_SUMMARY_TTL = timedelta(days=7)


def is_owned_playlist(
    playlist: PlaylistSummary,
    *,
    current_user_id: str | None,
    current_user_display_name: str | None = None,
) -> bool:
    """Return whether the current user can full-scan this playlist."""
    if playlist.track_count <= 0:
        return False
    if current_user_id and playlist.owner_id:
        return playlist.owner_id == current_user_id
    if current_user_id and current_user_display_name:
        return (
            playlist.owner.strip().casefold()
            == current_user_display_name.strip().casefold()
        )
    return playlist.can_edit


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
        """Serialize scan stats for API responses."""
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
    force_full: bool = False,
    auth: SpotifyJobAuth | None = None,
) -> PlaylistScanStats:
    """Scan every track in a playlist, paginating efficiently."""
    if playlist.track_count == 0:
        return _metadata_stats(playlist)

    if not force_full and not playlist.can_edit:
        return _metadata_stats(playlist)

    if use_cache:
        cached = _load_cached_stats(db, playlist_id=playlist.id)
        if cached is not None:
            if on_page is not None:
                on_page(cached.tracks_scanned)
            return cached

    tracks: list[TrackSummary] = []
    offset = 0
    client = sp
    while True:
        for attempt in range(2):
            try:
                page = client.playlist_items(
                    playlist.id,
                    limit=PAGE_SIZE,
                    offset=offset,
                    additional_types=["track"],
                )
                break
            except SpotifyException as exc:
                if exc.http_status == 429:
                    record_rate_limit(
                        db,
                        retry_after_seconds=retry_after_from_exception(exc),
                    )
                    raise
                if exc.http_status == 401 and auth is not None and attempt == 0:
                    auth.invalidate()
                    client = auth.client(db)
                    continue
                raise
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
    auth: SpotifyJobAuth,
    db_factory: Callable[[], Session],
    playlists: list[PlaylistSummary],
    max_workers: int = PARALLEL_SCAN_WORKERS,
    use_cache: bool = True,
    conservative: bool = False,
    on_playlist_start: Callable[[int, int, str, int], None] | None = None,
    on_playlist_page: Callable[[int, int], None] | None = None,
    on_playlist_done: Callable[[int, PlaylistScanStats], None] | None = None,
) -> list[PlaylistScanStats]:
    """Scan multiple owned playlists in parallel; metadata-only for others."""
    if not playlists:
        return []

    if conservative:
        max_workers = min(max_workers, CONSERVATIVE_SCAN_WORKERS)

    results: list[PlaylistScanStats | None] = [None] * len(playlists)

    def scan_at(index: int, playlist: PlaylistSummary) -> tuple[int, PlaylistScanStats]:
        if conservative and index > 0:
            time.sleep(0.35)
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

        db = db_factory()
        try:
            sp = auth.client(db)

            def page_cb(loaded: int) -> None:
                if on_playlist_page is not None:
                    on_playlist_page(index, loaded)

            stats = scan_playlist_full(
                sp,
                db,
                playlist=playlist,
                on_page=page_cb,
                use_cache=use_cache,
                auth=auth,
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


def resolve_playlists_to_scan(
    sp: spotipy.Spotify,
    *,
    current_user_id: str | None,
    options: CleanupSuggestOptions,
    cached_playlists: list[PlaylistSummary] | None = None,
    db: Session | None = None,
) -> tuple[list[PlaylistSummary], list[PlaylistSummary]]:
    """Return playlists to scan and the full library list for the chosen scope."""
    from app.cleanup.playlist_resolution import resolve_playlists_to_scan as resolve

    return resolve(
        sp,
        current_user_id=current_user_id,
        options=options,
        cached_playlists=cached_playlists,
        db=db,
    )


def filter_scans_by_thresholds(
    scans: list[PlaylistScanStats],
    *,
    options: CleanupSuggestOptions,
) -> list[PlaylistScanStats]:
    """Drop scan rows that do not meet minimum issue thresholds."""
    focus_areas = options.resolved_focus_areas()
    all_areas = len(focus_areas) >= len(ALL_FOCUS_AREAS)
    filtered: list[PlaylistScanStats] = []
    for scan in scans:
        has_dupes = scan.duplicate_tracks >= options.min_duplicates
        has_unavail = scan.unavailable_tracks >= options.min_unavailable
        is_bloated = scan.track_count >= options.min_bloated_tracks
        matches = False
        if all_areas:
            matches = has_dupes or has_unavail or is_bloated
        else:
            if "duplicates" in focus_areas and has_dupes:
                matches = True
            if "unavailable" in focus_areas and has_unavail:
                matches = True
            if "bloated" in focus_areas and is_bloated:
                matches = True
        if matches:
            filtered.append(scan)
    return filtered


def filter_scans_by_focus(
    scans: list[PlaylistScanStats],
    *,
    focus_areas: Sequence[str],
    min_bloated_tracks: int = 150,
) -> list[PlaylistScanStats]:
    """Narrow scan results to playlists with issues in the selected focus areas."""
    if len(focus_areas) >= len(ALL_FOCUS_AREAS):
        return scans

    filtered: list[PlaylistScanStats] = []
    for scan in scans:
        if "duplicates" in focus_areas and scan.duplicate_tracks > 0:
            filtered.append(scan)
            continue
        if "unavailable" in focus_areas and scan.unavailable_tracks > 0:
            filtered.append(scan)
            continue
        if "bloated" in focus_areas and scan.track_count >= min_bloated_tracks:
            filtered.append(scan)
    return filtered


def load_all_cached_stats(db: Session) -> dict[str, dict[str, Any]]:
    """Return cached scan stats keyed by playlist id."""
    records = db.query(PlaylistScanCacheRecord).all()
    summaries: dict[str, dict[str, Any]] = {}
    for record in records:
        age = utcnow() - ensure_utc(record.updated_at)
        if age > SCAN_SUMMARY_TTL:
            continue
        data = loads_json(record.scan_json)
        if not isinstance(data, dict):
            continue
        if not data.get("full_scan"):
            continue
        summaries[record.playlist_id] = data
    return summaries


def refresh_owned_playlist_scans(
    sp: spotipy.Spotify,
    db: Session,
    *,
    current_user_id: str | None,
    playlists: list[PlaylistSummary] | None = None,
    current_user_display_name: str | None = None,
) -> list[PlaylistScanStats]:
    """Full-scan every owned playlist and refresh cache."""
    if playlists is None:
        playlists = list_playlists(sp, current_user_id=current_user_id)
    owned = [
        playlist
        for playlist in playlists
        if is_owned_playlist(
            playlist,
            current_user_id=current_user_id,
            current_user_display_name=current_user_display_name,
        )
    ]
    logger.info("Starting cleanup scan for %s owned playlists", len(owned))
    results: list[PlaylistScanStats] = []
    for index, playlist in enumerate(owned, start=1):
        try:
            if not playlist.can_edit:
                playlist = playlist.model_copy(update={"can_edit": True})
            stats = scan_playlist_full(
                sp,
                db,
                playlist=playlist,
                use_cache=False,
                force_full=True,
            )
            results.append(stats)
            logger.info(
                "Scanned playlist %s/%s (%s): %s dupes, %s unavailable",
                index,
                len(owned),
                playlist.name,
                stats.duplicate_tracks,
                stats.unavailable_tracks,
            )
            time.sleep(0.35)
        except Exception:
            logger.exception("Failed to scan playlist %s", playlist.id)
    logger.info(
        "Cleanup scan finished: %s/%s playlists scanned", len(results), len(owned)
    )
    return results
