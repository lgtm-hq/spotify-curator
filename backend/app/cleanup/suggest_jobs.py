"""Background jobs for AI cleanup library scans."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

import spotipy
from sqlalchemy.orm import Session

from app.ai.budget import CostBudget
from app.ai.cli_schemas import cleanup_suggestions_schema
from app.ai.config import get_provider, load_ai_config
from app.ai.invoke import call_ai
from app.ai.json_response import load_json_object
from app.ai.prompts.cleanup import CLEANUP_SYSTEM, CLEANUP_USER_TEMPLATE
from app.cleanup.playlist_scan import (
    PlaylistScanStats,
    select_playlists_to_scan,
    scan_playlists_parallel,
)
from app.db import SessionLocal, TokenRecord
from app.taste.engine import load_cached_taste_profile
from app.taste.models import TasteProfile

logger = logging.getLogger(__name__)

_jobs: dict[str, SuggestJob] = {}
_jobs_lock = threading.Lock()


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
    status: str = "scanning"
    progress: ScanProgress = field(default_factory=ScanProgress)
    result: dict[str, Any] | None = None
    error: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "job_id": self.job_id,
                "status": self.status,
                "progress": self.progress.to_dict(),
                "result": self.result,
                "error": self.error,
            }

    def set_phase(self, phase: str) -> None:
        with self._lock:
            self.progress.phase = phase

    def on_playlist_start(
        self,
        index: int,
        total: int,
        name: str,
        track_total: int,
    ) -> None:
        with self._lock:
            self.progress.playlist_index = index
            self.progress.playlist_total = total
            self.progress.playlist_name = name
            self.progress.track_total = track_total
            self.progress.tracks_loaded = 0

    def on_playlist_page(self, loaded: int) -> None:
        with self._lock:
            self.progress.tracks_loaded = loaded

    def on_playlist_done(self) -> None:
        with self._lock:
            self.progress.playlists_completed += 1

    def complete(self, result: dict[str, Any]) -> None:
        with self._lock:
            self.status = "completed"
            self.result = result
            self.progress.phase = "done"

    def fail(self, message: str) -> None:
        with self._lock:
            self.status = "failed"
            self.error = message


def create_suggest_job() -> SuggestJob:
    """Register a new suggest job."""
    job = SuggestJob(job_id=str(uuid.uuid4()))
    with _jobs_lock:
        _jobs[job.job_id] = job
    return job


def get_suggest_job(job_id: str) -> SuggestJob | None:
    """Return a job by id."""
    with _jobs_lock:
        return _jobs.get(job_id)


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


def _generate_ai_suggestions(
    *,
    scans: list[PlaylistScanStats],
    total_playlists: int,
    taste_profile: TasteProfile,
) -> dict[str, Any]:
    scan_payload = [scan.to_dict() for scan in scans]
    ai_config = load_ai_config()
    if not ai_config.enabled or not scans:
        result = _heuristic_suggestions(scan_payload)
        result["scanned_playlists"] = len(scans)
        result["total_playlists"] = total_playlists
        return result

    import json

    provider = get_provider(ai_config)
    budget = CostBudget(max_cost_usd=ai_config.max_cost_usd)
    prompt = CLEANUP_USER_TEMPLATE.format(
        taste_profile=taste_profile.model_dump_json(),
        scanned_count=len(scans),
        total_playlists=total_playlists,
        playlist_scans=json.dumps(scan_payload, indent=2),
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
        parsed = _heuristic_suggestions(scan_payload)

    parsed["scanned_playlists"] = len(scans)
    parsed["total_playlists"] = total_playlists
    return parsed


def run_suggest_job(job_id: str, *, current_user_id: str) -> None:
    """Scan the full library and produce cleanup suggestions."""
    job = get_suggest_job(job_id)
    if job is None:
        return

    db = SessionLocal()
    try:
        token = db.get(TokenRecord, 1)
        if token is None:
            job.fail("Spotify not connected")
            return

        sp = spotipy.Spotify(auth=token.access_token)
        to_scan, all_playlists = select_playlists_to_scan(
            sp,
            current_user_id=current_user_id,
        )
        taste_profile = load_cached_taste_profile(db) or TasteProfile(
            summary="No cached taste profile.",
        )

        def on_start(index: int, total: int, name: str, track_total: int) -> None:
            job.on_playlist_start(index, total, name, track_total)

        def on_page(_index: int, loaded: int) -> None:
            job.on_playlist_page(loaded)

        def on_done(_index: int, _stats: PlaylistScanStats) -> None:
            job.on_playlist_done()

        scans = scan_playlists_parallel(
            access_token=token.access_token,
            db_factory=SessionLocal,
            playlists=to_scan,
            on_playlist_start=on_start,
            on_playlist_page=on_page,
            on_playlist_done=on_done,
        )

        job.set_phase("ai")
        result = _generate_ai_suggestions(
            scans=scans,
            total_playlists=len(all_playlists),
            taste_profile=taste_profile,
        )
        job.complete(result)
    except Exception as exc:
        logger.exception("Cleanup suggest job %s failed", job_id)
        job.fail(str(exc))
    finally:
        db.close()
