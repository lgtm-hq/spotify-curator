"""Background jobs for AI cleanup library scans."""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.ai.budget import CostBudget
from app.ai.cli_schemas import cleanup_suggestions_schema
from app.ai.config import get_provider, load_ai_config
from app.ai.invoke import call_ai
from app.ai.json_response import load_json_object
from app.ai.prompts.cleanup import CLEANUP_SYSTEM, CLEANUP_USER_TEMPLATE
from app.cleanup.advisor_presets import quick_start_context
from app.cleanup.playlist_scan import (
    PlaylistScanStats,
    filter_scans_by_focus,
    filter_scans_by_thresholds,
    resolve_playlists_to_scan,
    scan_playlists_parallel,
)
from app.cleanup.suggest_options import ALL_FOCUS_AREAS, CleanupSuggestOptions
from app.db import SessionLocal
from app.playlists.cache import load_playlist_list_cache, playlists_from_scan_cache
from app.spotify_client import SpotifyJobAuth
from app.taste.engine import load_cached_taste_profile
from app.taste.models import TasteProfile

logger = logging.getLogger(__name__)

_jobs: dict[str, SuggestJob] = {}
_jobs_lock = threading.Lock()

_FOCUS_HINTS = {
    "duplicates": (
        "\n\nFocus primarily on duplicate tracks and deduplication opportunities."
    ),
    "unavailable": "\n\nFocus primarily on unavailable or unplayable tracks.",
    "bloated": (
        "\n\nFocus primarily on oversized playlists that would benefit "
        "from splitting or trimming."
    ),
}


def _focus_hint_for_areas(focus_areas: Sequence[str]) -> str:
    """Build combined AI focus hint for selected areas."""
    if len(focus_areas) >= len(ALL_FOCUS_AREAS):
        return ""
    return "".join(_FOCUS_HINTS[area] for area in focus_areas if area in _FOCUS_HINTS)


@dataclass
class ScanProgress:
    """Live progress for a cleanup suggest job."""

    phase: str = "scanning"
    playlist_index: int = 0
    playlist_total: int = 0
    playlist_name: str = ""
    track_total: int = 0
    tracks_loaded: int = 0
    playlists_completed: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize progress for API responses."""
        return {
            "phase": self.phase,
            "playlist_index": self.playlist_index,
            "playlist_total": self.playlist_total,
            "playlist_name": self.playlist_name,
            "track_total": self.track_total,
            "tracks_loaded": self.tracks_loaded,
            "playlists_completed": self.playlists_completed,
        }


@dataclass
class SuggestJob:
    """In-memory cleanup suggestion job."""

    job_id: str
    options: CleanupSuggestOptions = field(default_factory=CleanupSuggestOptions)
    status: str = "scanning"
    progress: ScanProgress = field(default_factory=ScanProgress)
    result: dict[str, Any] | None = None
    error: str | None = None
    cancelled: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize job state for API responses."""
        with self._lock:
            return {
                "job_id": self.job_id,
                "status": self.status,
                "progress": self.progress.to_dict(),
                "result": self.result,
                "error": self.error,
                "options": self.options.model_dump(),
            }

    def is_cancelled(self) -> bool:
        """Return whether the job has been cancelled."""
        with self._lock:
            return self.cancelled

    def cancel(self) -> bool:
        """Cancel the job; return False if already finished."""
        with self._lock:
            if self.status in {"completed", "failed", "cancelled"}:
                return False
            self.cancelled = True
            self.status = "cancelled"
            self.error = "Scan cancelled."
            self.progress.phase = "cancelled"
            return True

    def set_phase(self, phase: str) -> None:
        """Set the current progress phase."""
        with self._lock:
            self.progress.phase = phase

    def on_playlist_start(
        self,
        index: int,
        total: int,
        name: str,
        track_total: int,
    ) -> None:
        """Record the start of a playlist scan."""
        with self._lock:
            self.progress.playlist_index = index
            self.progress.playlist_total = total
            self.progress.playlist_name = name
            self.progress.track_total = track_total
            self.progress.tracks_loaded = 0

    def on_playlist_page(self, loaded: int) -> None:
        """Update the number of tracks loaded for the current playlist."""
        with self._lock:
            self.progress.tracks_loaded = loaded

    def on_playlist_done(self) -> None:
        """Mark the current playlist scan as complete."""
        with self._lock:
            self.progress.playlists_completed += 1

    def complete(self, result: dict[str, Any]) -> None:
        """Mark the job as completed with its result payload."""
        with self._lock:
            self.status = "completed"
            self.result = result
            self.progress.phase = "done"

    def fail(self, message: str) -> None:
        """Mark the job as failed with an error message."""
        with self._lock:
            self.status = "failed"
            self.error = message


def create_suggest_job(*, options: CleanupSuggestOptions | None = None) -> SuggestJob:
    """Register a new suggest job."""
    job = SuggestJob(
        job_id=str(uuid.uuid4()),
        options=options or CleanupSuggestOptions(),
    )
    with _jobs_lock:
        _jobs[job.job_id] = job
    return job


def get_suggest_job(job_id: str) -> SuggestJob | None:
    """Return a job by id."""
    with _jobs_lock:
        return _jobs.get(job_id)


def cancel_suggest_job(job_id: str) -> bool:
    """Request cancellation of a running suggest job."""
    job = get_suggest_job(job_id)
    if job is None:
        return False
    return job.cancel()


def _heuristic_suggestions(
    scans: list[dict[str, Any]],
    *,
    options: CleanupSuggestOptions,
) -> dict[str, Any]:
    """Build fallback suggestions without AI."""
    suggestions: list[dict[str, Any]] = []

    for scan in scans:
        playlist_id = str(scan["playlist_id"])
        playlist_name = str(scan["playlist_name"])
        duplicates = int(scan.get("duplicate_tracks") or 0)
        unavailable = int(scan.get("unavailable_tracks") or 0)
        track_count = int(scan.get("track_count") or 0)

        if duplicates > 0 and duplicates >= options.min_duplicates:
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
                    "recommended_action": (
                        "Expand to review and remove duplicate tracks."
                    ),
                },
            )

        if unavailable > 0 and unavailable >= options.min_unavailable:
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
                    "recommended_action": (
                        "Expand to review and remove unavailable tracks."
                    ),
                },
            )

        if track_count >= options.min_bloated_tracks:
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


def _generate_ai_suggestions(
    *,
    scans: list[PlaylistScanStats],
    total_playlists: int,
    taste_profile: TasteProfile,
    options: CleanupSuggestOptions,
) -> dict[str, Any]:
    scan_payload = [scan.to_dict() for scan in scans]
    ai_config = load_ai_config()
    if not ai_config.enabled or not scans:
        result = _heuristic_suggestions(scan_payload, options=options)
        result["scanned_playlists"] = len(scans)
        result["total_playlists"] = total_playlists
        return result

    import json

    provider = get_provider(ai_config)
    budget = CostBudget(max_cost_usd=ai_config.max_cost_usd)
    focus_hint = _focus_hint_for_areas(options.resolved_focus_areas())
    user_instructions = ""
    approach = quick_start_context(options.quick_start_id)
    if approach:
        user_instructions = f"\n\nAdvisor approach:\n{approach}"
    if options.user_prompt and options.user_prompt.strip():
        user_instructions += (
            f"\n\nAdditional user instructions:\n{options.user_prompt.strip()}"
        )
    taste_payload = taste_profile.model_dump_json()
    if not options.include_taste_profile:
        taste_payload = '{"summary":"Taste profile omitted by user request."}'
    elif options.custom_taste_summary and options.custom_taste_summary.strip():
        taste_payload = json.dumps(
            {
                **taste_profile.model_dump(),
                "summary": options.custom_taste_summary.strip(),
                "user_override": True,
            },
        )

    prompt = CLEANUP_USER_TEMPLATE.format(
        taste_profile=taste_payload,
        scanned_count=len(scans),
        total_playlists=total_playlists,
        playlist_scans=json.dumps(scan_payload, indent=2),
        focus_hint=focus_hint,
        user_instructions=user_instructions,
    )
    cli_schema = (
        cleanup_suggestions_schema()
        if ai_config.transport and ai_config.transport.value == "cli"
        else None
    )
    try:
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
        parsed = _heuristic_suggestions(scan_payload, options=options)

    parsed["scanned_playlists"] = len(scans)
    parsed["total_playlists"] = total_playlists
    return parsed


def run_suggest_job(job_id: str, *, current_user_id: str) -> None:
    """Scan playlists and produce cleanup suggestions."""
    job = get_suggest_job(job_id)
    if job is None:
        return

    options = job.options
    db = SessionLocal()
    try:
        if job.is_cancelled():
            return

        try:
            auth = SpotifyJobAuth(SessionLocal)
            sp = auth.client(db)
        except Exception:
            job.fail("Spotify not connected")
            return
        cached_playlists = load_playlist_list_cache(db) or playlists_from_scan_cache(db)
        to_scan, all_playlists = resolve_playlists_to_scan(
            sp,
            current_user_id=current_user_id,
            options=options,
            cached_playlists=cached_playlists,
            db=db,
        )

        if options.scope == "selected" and not to_scan:
            job.fail(
                "No matching playlists selected. "
                "Refresh your playlist list on Dashboard.",
            )
            return

        if not to_scan:
            job.fail("No playlists matched your scan settings.")
            return

        taste_profile = load_cached_taste_profile(db) or TasteProfile(
            summary="No cached taste profile.",
        )
        if not options.include_taste_profile:
            taste_profile = TasteProfile(summary="Taste profile omitted for this run.")

        def on_start(index: int, total: int, name: str, track_total: int) -> None:
            job.on_playlist_start(index, total, name, track_total)

        def on_page(_index: int, loaded: int) -> None:
            job.on_playlist_page(loaded)

        def on_done(_index: int, _stats: PlaylistScanStats) -> None:
            job.on_playlist_done()

        scans = scan_playlists_parallel(
            auth=auth,
            db_factory=SessionLocal,
            playlists=to_scan,
            use_cache=options.effective_use_cache(),
            conservative=options.conservative_scan,
            on_playlist_start=on_start,
            on_playlist_page=on_page,
            on_playlist_done=on_done,
        )
        if job.is_cancelled():
            return

        scans = filter_scans_by_focus(
            scans,
            focus_areas=options.resolved_focus_areas(),
            min_bloated_tracks=options.min_bloated_tracks,
        )
        scans = filter_scans_by_thresholds(scans, options=options)

        if job.is_cancelled():
            return

        job.set_phase("ai")
        result = _generate_ai_suggestions(
            scans=scans,
            total_playlists=len(all_playlists),
            taste_profile=taste_profile,
            options=options,
        )
        result["scan_options"] = options.model_dump()
        if job.is_cancelled():
            return
        job.complete(result)
    except Exception as exc:
        if job.is_cancelled():
            return
        logger.exception("Cleanup suggest job %s failed", job_id)
        job.fail(str(exc))
    finally:
        db.close()
