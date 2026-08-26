"""Discover API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.router import get_current_user, get_db
from app.db import DiscoverRunRecord, User
from app.discover.service import (
    delete_discovery_run,
    generate_discovery_proposal,
    get_discovery_run,
    remove_discovery_run,
    save_discovery_run_to_spotify,
)
from app.spotify_client import get_spotify_client

router = APIRouter(prefix="/discover", tags=["discover"])


class DiscoverSaveRequest(BaseModel):
    """Request to save an approved discovery proposal to Spotify."""

    track_uris: list[str] = Field(default_factory=list)


class DiscoverRemoveRequest(BaseModel):
    """Request to remove a discovery run and/or its Spotify playlist."""

    remove_history: bool = True
    delete_playlist: bool = False


@router.post("/generate")
async def discover_generate(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate a discovery playlist proposal for user review."""
    sp = await get_spotify_client(db)
    try:
        return generate_discovery_proposal(sp, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{run_id}")
async def discover_run_detail(
    run_id: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return full discovery run details including tracks and rationale."""
    try:
        sp = await get_spotify_client(db)
        return get_discovery_run(db, run_id=run_id, sp=sp)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/runs/{run_id}")
async def discover_run_delete(
    run_id: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete a discovery run from history (history only)."""
    try:
        delete_discovery_run(db, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.post("/runs/{run_id}/remove")
async def discover_run_remove(
    run_id: str,
    body: DiscoverRemoveRequest,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Remove a discovery run from history and/or delete its Spotify playlist."""
    sp = await get_spotify_client(db) if body.delete_playlist else None
    try:
        return remove_discovery_run(
            db,
            run_id=run_id,
            sp=sp,
            remove_history=body.remove_history,
            delete_playlist=body.delete_playlist,
        )
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/runs/{run_id}/save")
async def discover_run_save(
    run_id: str,
    body: DiscoverSaveRequest,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create the Spotify playlist after user approval."""
    sp = await get_spotify_client(db)
    try:
        return save_discovery_run_to_spotify(
            sp,
            db=db,
            run_id=run_id,
            track_uris=body.track_uris or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/history")
async def discover_history(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List past discovery runs."""
    runs = (
        db.query(DiscoverRunRecord)
        .order_by(DiscoverRunRecord.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "run_id": run.id,
            "playlist_id": run.playlist_id,
            "name": run.playlist_name,
            "status": _history_status(run),
            "track_count": _track_count(run),
            "created_at": run.created_at.isoformat(),
            "legacy_auto_saved": _is_legacy_auto_saved(run),
        }
        for run in runs
    ]


def _history_status(record: DiscoverRunRecord) -> str:
    status = record.status or "pending"
    if status == "saved" and not record.playlist_id:
        return "pending"
    if not status and record.playlist_id:
        return "saved"
    return status


def _track_count(record: DiscoverRunRecord) -> int:
    from app.db import loads_json

    payload = loads_json(record.tracks_json)
    if not isinstance(payload, dict):
        return 0
    tracks = payload.get("tracks", [])
    uris = payload.get("uris", [])
    if isinstance(tracks, list) and tracks:
        return len(tracks)
    if isinstance(uris, list):
        return len(uris)
    return 0


def _is_legacy_auto_saved(record: DiscoverRunRecord) -> bool:
    """True for runs created before the review-before-save flow."""
    from app.db import loads_json

    if not record.playlist_id:
        return False
    payload = loads_json(record.tracks_json)
    if not isinstance(payload, dict):
        return True
    return "rationale" not in payload
