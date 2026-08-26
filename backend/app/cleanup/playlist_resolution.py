"""Resolve, sort, and estimate playlist scans for the AI advisor."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import spotipy
from sqlalchemy.orm import Session

from app.cleanup.suggest_options import CleanupSuggestOptions
from app.db import PlaylistScanCacheRecord, ensure_utc, utcnow
from app.playlists.models import PlaylistSummary
from app.playlists.service import list_playlists

PAGE_SIZE = 100
SECONDS_PER_API_CALL = 0.35
SECONDS_PER_PLAYLIST_OVERHEAD = 1.5
SCAN_CACHE_TTL = timedelta(hours=1)


def _scan_cache_ages(db: Session | None) -> dict[str, datetime]:
    """Return playlist id -> updated_at for all cached scans."""
    if db is None:
        return {}
    ages: dict[str, datetime] = {}
    for record in db.query(PlaylistScanCacheRecord).all():
        ages[record.playlist_id] = ensure_utc(record.updated_at)
    return ages


def _is_stale(
    playlist_id: str,
    *,
    stale_after_days: int,
    cache_ages: dict[str, datetime],
) -> bool:
    """Return True when a playlist has no cache or cache is older than the threshold."""
    scanned_at = cache_ages.get(playlist_id)
    if scanned_at is None:
        return True
    age = utcnow() - scanned_at
    return age > timedelta(days=stale_after_days)


def _apply_scope(
    eligible: list[PlaylistSummary],
    *,
    options: CleanupSuggestOptions,
) -> list[PlaylistSummary]:
    if options.scope == "all_owned":
        return [playlist for playlist in eligible if playlist.can_edit]
    if options.scope == "selected":
        selected = set(options.playlist_ids)
        return [playlist for playlist in eligible if playlist.id in selected]
    return list(eligible)


def _apply_excludes(
    playlists: list[PlaylistSummary],
    *,
    options: CleanupSuggestOptions,
) -> list[PlaylistSummary]:
    if not options.exclude_playlist_ids:
        return playlists
    excluded = set(options.exclude_playlist_ids)
    return [playlist for playlist in playlists if playlist.id not in excluded]


def _apply_stale_filter(
    playlists: list[PlaylistSummary],
    *,
    options: CleanupSuggestOptions,
    cache_ages: dict[str, datetime],
) -> list[PlaylistSummary]:
    if options.stale_after_days is None:
        return playlists
    return [
        playlist
        for playlist in playlists
        if _is_stale(
            playlist.id,
            stale_after_days=options.stale_after_days,
            cache_ages=cache_ages,
        )
    ]


def _sort_playlists(
    playlists: list[PlaylistSummary],
    *,
    options: CleanupSuggestOptions,
    cache_ages: dict[str, datetime],
) -> list[PlaylistSummary]:
    sort_by = options.sort_by
    if sort_by == "track_count_desc":
        return sorted(playlists, key=lambda item: item.track_count, reverse=True)
    if sort_by == "track_count_asc":
        return sorted(playlists, key=lambda item: item.track_count)
    if sort_by == "name_asc":
        return sorted(playlists, key=lambda item: item.name.lower())
    if sort_by == "name_desc":
        return sorted(playlists, key=lambda item: item.name.lower(), reverse=True)
    if sort_by == "stale_first":

        def stale_key(item: PlaylistSummary) -> tuple[int, float]:
            scanned_at = cache_ages.get(item.id)
            if scanned_at is None:
                return (0, 0.0)
            return (1, scanned_at.timestamp())

        return sorted(playlists, key=stale_key)
    if sort_by == "recently_scanned":

        def recent_key(item: PlaylistSummary) -> tuple[int, float]:
            scanned_at = cache_ages.get(item.id)
            if scanned_at is None:
                return (0, 0.0)
            return (1, scanned_at.timestamp())

        return sorted(playlists, key=recent_key, reverse=True)
    return playlists


def resolve_playlists_to_scan(
    sp: spotipy.Spotify,
    *,
    current_user_id: str | None,
    options: CleanupSuggestOptions,
    cached_playlists: list[PlaylistSummary] | None = None,
    db: Session | None = None,
) -> tuple[list[PlaylistSummary], list[PlaylistSummary]]:
    """Return playlists to scan and the full library list for the chosen scope."""
    all_playlists = cached_playlists or list_playlists(
        sp, current_user_id=current_user_id
    )
    eligible = [
        playlist
        for playlist in all_playlists
        if playlist.track_count >= options.min_track_count
    ]
    cache_ages = _scan_cache_ages(db)

    to_scan = _apply_scope(eligible, options=options)
    to_scan = _apply_excludes(to_scan, options=options)
    to_scan = _apply_stale_filter(to_scan, options=options, cache_ages=cache_ages)
    to_scan = _sort_playlists(to_scan, options=options, cache_ages=cache_ages)
    return to_scan, all_playlists


def estimate_scan(
    playlists: list[PlaylistSummary],
    *,
    options: CleanupSuggestOptions,
    db: Session | None = None,
) -> dict[str, int | float]:
    """Estimate Spotify API usage and runtime for a scan configuration."""
    cache_ages = _scan_cache_ages(db)
    use_cache = options.effective_use_cache()

    cached_count = 0
    fresh_count = 0
    estimated_api_calls = 0
    estimated_track_pages = 0

    for playlist in playlists:
        if not playlist.can_edit or playlist.track_count == 0:
            continue
        scanned_at = cache_ages.get(playlist.id)
        cache_is_fresh = (
            use_cache
            and scanned_at is not None
            and utcnow() - scanned_at <= SCAN_CACHE_TTL
        )
        if cache_is_fresh:
            cached_count += 1
            continue
        fresh_count += 1
        pages = max(1, math.ceil(playlist.track_count / PAGE_SIZE))
        estimated_api_calls += pages
        estimated_track_pages += pages

    workers = 2 if options.conservative_scan else 4
    parallel_batches = math.ceil(fresh_count / workers) if fresh_count else 0
    scan_seconds = (
        parallel_batches * (SECONDS_PER_PLAYLIST_OVERHEAD + SECONDS_PER_API_CALL)
        + estimated_track_pages * SECONDS_PER_API_CALL * 0.25
    )
    ai_seconds = 8 if fresh_count > 0 else 2

    total_min = max(5, int(scan_seconds + ai_seconds))
    total_max = int(total_min * 1.6) + 5

    return {
        "playlist_count": len(playlists),
        "cached_count": cached_count,
        "fresh_scan_count": fresh_count,
        "estimated_api_calls": estimated_api_calls,
        "estimated_seconds_min": total_min,
        "estimated_seconds_max": total_max,
    }
