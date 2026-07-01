"""AI-powered cleanup suggestions across the playlist library."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import spotipy
from sqlalchemy.orm import Session

from app.ai.budget import CostBudget
from app.ai.cli_schemas import cleanup_suggestions_schema
from app.ai.config import get_provider, load_ai_config
from app.ai.invoke import call_ai
from app.ai.json_response import load_json_object
from app.ai.prompts.cleanup import CLEANUP_SYSTEM, CLEANUP_USER_TEMPLATE
from app.cleanup.service import find_duplicates, find_unavailable
from app.playlists.models import PlaylistSummary
from app.playlists.service import fetch_playlist_tracks_lite, list_playlists
from app.taste.engine import load_cached_taste_profile
from app.taste.models import TasteProfile

logger = logging.getLogger(__name__)

MAX_SCANNED_PLAYLISTS = 10
MAX_TRACKS_PER_QUICK_SCAN = 100


def _metadata_scan(playlist: PlaylistSummary) -> dict[str, Any]:
    """Build scan stats from playlist metadata only."""
    return {
        "playlist_id": playlist.id,
        "playlist_name": playlist.name,
        "track_count": playlist.track_count,
        "duplicate_tracks": 0,
        "unavailable_tracks": 0,
        "owned": playlist.can_edit,
        "sampled_tracks": 0,
    }


def _quick_scan_playlist(
    sp: spotipy.Spotify,
    *,
    playlist: PlaylistSummary,
) -> dict[str, Any]:
    """Run a lightweight duplicate/unavailable scan on one owned playlist."""
    if playlist.track_count == 0 or not playlist.can_edit:
        return _metadata_scan(playlist)

    tracks = fetch_playlist_tracks_lite(
        sp,
        playlist_id=playlist.id,
        max_tracks=MAX_TRACKS_PER_QUICK_SCAN,
    )
    duplicate_issues = find_duplicates(tracks)
    unavailable_issues = find_unavailable(tracks)

    duplicate_ids: set[str] = set()
    for issue in duplicate_issues:
        duplicate_ids.update(issue.track_ids)

    unavailable_ids: set[str] = set()
    for issue in unavailable_issues:
        unavailable_ids.update(issue.track_ids)

    return {
        "playlist_id": playlist.id,
        "playlist_name": playlist.name,
        "track_count": playlist.track_count,
        "duplicate_tracks": len(duplicate_ids),
        "unavailable_tracks": len(unavailable_ids),
        "owned": True,
        "sampled_tracks": len(tracks),
    }


def _heuristic_suggestions(scans: list[dict[str, Any]]) -> dict[str, Any]:
    """Build fallback suggestions without AI."""
    suggestions: list[dict[str, Any]] = []

    for scan in scans:
        playlist_id = str(scan["playlist_id"])
        playlist_name = str(scan["playlist_name"])
        duplicates = int(scan.get("duplicate_tracks") or 0)
        unavailable = int(scan.get("unavailable_tracks") or 0)
        track_count = int(scan.get("track_count") or 0)

        if duplicates > 0:
            suggestions.append(
                {
                    "playlist_id": playlist_id,
                    "playlist_name": playlist_name,
                    "priority": "high" if duplicates >= 5 else "medium",
                    "kind": "duplicates",
                    "title": f"Remove {duplicates} duplicates",
                    "description": (
                        f"'{playlist_name}' has {duplicates} duplicate tracks "
                        f"that can be cleaned up."
                    ),
                    "recommended_action": "Expand to review and remove duplicate tracks.",
                },
            )

        if unavailable > 0:
            suggestions.append(
                {
                    "playlist_id": playlist_id,
                    "playlist_name": playlist_name,
                    "priority": "high",
                    "kind": "unavailable",
                    "title": f"Remove {unavailable} unavailable tracks",
                    "description": (
                        f"'{playlist_name}' contains {unavailable} tracks that "
                        "are not playable in your market."
                    ),
                    "recommended_action": "Expand to review and remove unavailable tracks.",
                },
            )

        if track_count >= 150:
            suggestions.append(
                {
                    "playlist_id": playlist_id,
                    "playlist_name": playlist_name,
                    "priority": "medium",
                    "kind": "split",
                    "title": "Split this large playlist",
                    "description": (
                        f"'{playlist_name}' has {track_count} tracks and may "
                        "benefit from mood-based splitting."
                    ),
                    "recommended_action": "Expand to review split proposals.",
                },
            )

    summary = (
        f"Found {len(suggestions)} cleanup opportunities across "
        f"{len(scans)} scanned playlists."
        if suggestions
        else "No obvious cleanup issues found in scanned playlists."
    )
    return {"summary": summary, "suggestions": suggestions}


def suggest_library_cleanups(
    sp: spotipy.Spotify,
    *,
    db: Session,
    current_user_id: str | None = None,
    taste_profile: TasteProfile | None = None,
) -> dict[str, Any]:
    """Scan playlists and return AI cleanup suggestions."""
    started = time.monotonic()
    if taste_profile is None:
        taste_profile = load_cached_taste_profile(db) or TasteProfile(
            summary="No cached taste profile.",
        )

    playlists = list_playlists(sp, current_user_id=current_user_id)
    playlists.sort(key=lambda item: item.track_count, reverse=True)
    to_scan = [p for p in playlists if p.track_count > 0][:MAX_SCANNED_PLAYLISTS]

    scans: list[dict[str, Any]] = []
    for index, playlist in enumerate(to_scan, start=1):
        try:
            logger.info(
                "Cleanup quick scan %d/%d: %s (%d tracks)",
                index,
                len(to_scan),
                playlist.name,
                playlist.track_count,
            )
            scans.append(_quick_scan_playlist(sp, playlist=playlist))
        except Exception:
            logger.exception("Quick scan failed for playlist %s", playlist.id)
            scans.append(_metadata_scan(playlist))

    scan_seconds = time.monotonic() - started
    logger.info("Cleanup quick scan finished in %.1fs", scan_seconds)

    ai_config = load_ai_config()
    if not ai_config.enabled or not scans:
        result = _heuristic_suggestions(scans)
        result["scanned_playlists"] = len(scans)
        result["total_playlists"] = len(playlists)
        return result

    provider = get_provider(ai_config)
    budget = CostBudget(max_cost_usd=ai_config.max_cost_usd)
    prompt = CLEANUP_USER_TEMPLATE.format(
        taste_profile=taste_profile.model_dump_json(),
        scanned_count=len(scans),
        total_playlists=len(playlists),
        playlist_scans=json.dumps(scans, indent=2),
    )
    cli_schema = (
        cleanup_suggestions_schema()
        if ai_config.transport and ai_config.transport.value == "cli"
        else None
    )
    try:
        logger.info("Requesting AI cleanup suggestions")
        response = call_ai(
            provider=provider,
            ai_config=ai_config,
            user_prompt=prompt,
            system_prompt=CLEANUP_SYSTEM,
            budget=budget,
            cli_schema=cli_schema,
        )
        parsed = load_json_object(content=response.content)
    except Exception:
        logger.exception("AI cleanup suggestions failed; using heuristic fallback")
        parsed = _heuristic_suggestions(scans)

    parsed["scanned_playlists"] = len(scans)
    parsed["total_playlists"] = len(playlists)
    logger.info("Cleanup suggest total time %.1fs", time.monotonic() - started)
    return parsed
