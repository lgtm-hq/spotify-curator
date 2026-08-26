"""Cleanup API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.router import get_current_user, get_db
from app.cleanup.advisor_presets import delete_preset, list_presets, save_preset
from app.cleanup.advisor_schedule import (
    get_schedule,
    list_schedule_runs,
    update_schedule,
)
from app.cleanup.playlist_resolution import estimate_scan, resolve_playlists_to_scan
from app.cleanup.service import (
    CleanupAnalysis,
    CleanupIssue,
    SplitProposal,
    analyze_playlist,
    apply_removals,
    apply_split,
)
from app.cleanup.suggest_jobs import (
    cancel_suggest_job,
    create_suggest_job,
    get_suggest_job,
    run_suggest_job,
)
from app.cleanup.suggest_options import CleanupSuggestOptions
from app.db import TokenRecord, User
from app.playlists.cache import load_playlist_list_cache, playlist_cache_updated_at
from app.spotify_client import call_spotify, create_spotify_client, get_spotify_client
from app.spotify_usage import usage_status

router = APIRouter(prefix="/cleanup", tags=["cleanup"])


def _issue_payload(issue: CleanupIssue) -> dict[str, Any]:
    return {
        "kind": issue.kind,
        "track_ids": issue.track_ids,
        "reason": issue.reason,
        "tracks": [track.model_dump() for track in issue.tracks],
    }


def _reject_if_rate_limited(db: Session) -> None:
    usage = usage_status(db, last_fetched_at=playlist_cache_updated_at(db))
    if usage["state"] == "limited":
        reset = usage["seconds_until_reset"]
        raise HTTPException(
            status_code=429,
            detail=(
                f"Spotify rate limit active. Try again in {reset} seconds."
                if reset is not None
                else "Spotify rate limit active. Try again later."
            ),
        )


@router.post("/ai/suggest")
async def start_ai_suggest(
    body: CleanupSuggestOptions,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Start a background library scan and AI cleanup suggestion job."""
    _reject_if_rate_limited(db)
    if body.scope == "selected" and not body.playlist_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "Select at least one playlist or switch scope to all owned playlists."
            ),
        )
    job = create_suggest_job(options=body)
    background_tasks.add_task(
        run_suggest_job,
        job.job_id,
        current_user_id=current_user.spotify_id,
    )
    return {"job_id": job.job_id, "status": job.status, "options": body.model_dump()}


class AdvisorPresetCreate(BaseModel):
    """Save current advisor options as a named preset."""

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)
    options: CleanupSuggestOptions


class AdvisorScheduleUpdate(BaseModel):
    """Update scheduled advisor configuration."""

    enabled: bool = False
    cron: str = Field(default="0 9 * * 0", max_length=64)
    options: CleanupSuggestOptions = Field(default_factory=CleanupSuggestOptions)
    notify_email: bool = True


@router.get("/ai/presets")
async def get_advisor_presets(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List built-in and user-saved advisor presets."""
    return {"presets": list_presets(db)}


@router.post("/ai/presets")
async def create_advisor_preset(
    body: AdvisorPresetCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Save advisor scan settings as a reusable preset."""
    return save_preset(
        db,
        name=body.name,
        description=body.description,
        options=body.options,
    )


@router.delete("/ai/presets/{preset_id}")
async def remove_advisor_preset(
    preset_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a user-saved preset."""
    if not delete_preset(db, preset_id):
        raise HTTPException(status_code=404, detail="Preset not found or built-in")
    return {"status": "deleted"}


@router.get("/ai/schedule")
async def get_advisor_schedule(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return scheduled advisor configuration."""
    return get_schedule(db)


@router.put("/ai/schedule")
async def put_advisor_schedule(
    body: AdvisorScheduleUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Enable or update the scheduled advisor run."""
    return update_schedule(
        db,
        enabled=body.enabled,
        cron=body.cron,
        options=body.options,
        notify_email=body.notify_email,
    )


@router.get("/ai/schedule/runs")
async def get_advisor_schedule_runs(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return recent scheduled advisor run history."""
    return {"runs": list_schedule_runs(db)}


@router.post("/ai/estimate")
async def estimate_advisor_scan(
    body: CleanupSuggestOptions,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Estimate API usage and runtime for advisor scan settings."""
    token = db.get(TokenRecord, 1)
    if token is None:
        raise HTTPException(status_code=401, detail="Spotify not connected")
    sp = create_spotify_client(token.access_token)
    cached_playlists = load_playlist_list_cache(db)
    to_scan, _all = resolve_playlists_to_scan(
        sp,
        current_user_id=current_user.spotify_id,
        options=body,
        cached_playlists=cached_playlists,
        db=db,
    )
    return estimate_scan(to_scan, options=body, db=db)


@router.post("/ai/suggest/jobs/{job_id}/cancel")
async def cancel_ai_suggest_job(
    job_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancel a running cleanup suggestion job."""
    if not cancel_suggest_job(job_id):
        raise HTTPException(status_code=404, detail="Cleanup job not found")
    job = get_suggest_job(job_id)
    return job.to_dict() if job else {"job_id": job_id, "status": "cancelled"}


@router.get("/ai/suggest/jobs/{job_id}")
async def get_ai_suggest_job(
    job_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Poll cleanup suggestion job progress and results."""
    job = get_suggest_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Cleanup job not found")
    return job.to_dict()


class RemoveRequest(BaseModel):
    """Request to remove tracks."""

    playlist_id: str
    track_ids: list[str] = Field(default_factory=list)


class SplitRequest(BaseModel):
    """Request to split playlist."""

    source_playlist_id: str
    proposals: list[dict[str, Any]]


@router.post("/analyze/{playlist_id}")
async def analyze(
    playlist_id: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Analyze a playlist for cleanup opportunities."""
    _reject_if_rate_limited(db)
    sp = await get_spotify_client(db)
    result: CleanupAnalysis = await analyze_playlist(sp, playlist_id=playlist_id, db=db)
    return {
        "playlist_id": result.playlist_id,
        "total_tracks": result.total_tracks,
        "duplicates": [_issue_payload(issue) for issue in result.duplicates],
        "unavailable": [_issue_payload(issue) for issue in result.unavailable],
        "skip_heavy": [_issue_payload(issue) for issue in result.skip_heavy],
        "clusters": [
            {"name": c.name, "track_ids": c.track_ids, "cluster_label": c.cluster_label}
            for c in result.clusters
        ],
    }


@router.post("/apply/remove")
async def remove_tracks(
    body: RemoveRequest,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Remove tracks from a playlist."""
    sp = await get_spotify_client(db)
    return apply_removals(
        sp,
        playlist_id=body.playlist_id,
        track_ids=body.track_ids,
        db=db,
    )


@router.post("/apply/split")
async def split_playlist(
    body: SplitRequest,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create split playlists from cluster proposals."""
    sp = await get_spotify_client(db)
    me = await call_spotify(sp.me)
    proposals = [
        SplitProposal(
            name=p["name"],
            track_ids=p["track_ids"],
            cluster_label=p["cluster_label"],
        )
        for p in body.proposals
    ]
    created = apply_split(
        sp,
        source_playlist_id=body.source_playlist_id,
        proposals=proposals,
        user_id=me["id"],
        db=db,
    )
    return {"created": created}
