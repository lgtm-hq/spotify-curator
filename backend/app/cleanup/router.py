"""Cleanup API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.router import get_current_user, get_db
from app.cleanup.service import (
    CleanupAnalysis,
    SplitProposal,
    analyze_playlist,
    apply_removals,
    apply_split,
)
from app.cleanup.suggest_jobs import create_suggest_job, get_suggest_job, run_suggest_job
from app.spotify_client import get_spotify_client

router = APIRouter(prefix="/cleanup", tags=["cleanup"])


@router.post("/ai/suggest")
async def start_ai_suggest(
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Start a background library scan and AI cleanup suggestion job."""
    job = create_suggest_job()
    background_tasks.add_task(run_suggest_job, job.job_id, current_user_id=user_id)
    return {"job_id": job.job_id, "status": job.status}


@router.get("/ai/suggest/jobs/{job_id}")
async def get_ai_suggest_job(
    job_id: str,
    _user: str = Depends(get_current_user),
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
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Analyze a playlist for cleanup opportunities."""
    sp = await get_spotify_client(db)
    result: CleanupAnalysis = await analyze_playlist(sp, playlist_id=playlist_id, db=db)
    return {
        "playlist_id": result.playlist_id,
        "total_tracks": result.total_tracks,
        "duplicates": [
            {"kind": i.kind, "track_ids": i.track_ids, "reason": i.reason}
            for i in result.duplicates
        ],
        "unavailable": [
            {"kind": i.kind, "track_ids": i.track_ids, "reason": i.reason}
            for i in result.unavailable
        ],
        "skip_heavy": [
            {"kind": i.kind, "track_ids": i.track_ids, "reason": i.reason}
            for i in result.skip_heavy
        ],
        "clusters": [
            {"name": c.name, "track_ids": c.track_ids, "cluster_label": c.cluster_label}
            for c in result.clusters
        ],
    }


@router.post("/apply/remove")
async def remove_tracks(
    body: RemoveRequest,
    _user: str = Depends(get_current_user),
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
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create split playlists from cluster proposals."""
    sp = await get_spotify_client(db)
    me = sp.me()
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
