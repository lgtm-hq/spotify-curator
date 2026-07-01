"""Cleanup API routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.router import get_current_user, get_db
from app.cleanup.ai_service import suggest_library_cleanups
from app.cleanup.service import (
    CleanupAnalysis,
    SplitProposal,
    analyze_playlist,
    apply_removals,
    apply_split,
)
from app.errors import raise_curate_http_error
from app.spotify_client import get_spotify_client

router = APIRouter(prefix="/cleanup", tags=["cleanup"])


@router.post("/ai/suggest")
async def ai_suggest(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Scan the library and return AI cleanup suggestions."""
    try:
        sp = await get_spotify_client(db)
        return await asyncio.to_thread(
            suggest_library_cleanups,
            sp,
            db=db,
            current_user_id=user_id,
        )
    except Exception as exc:
        raise_curate_http_error(exc, action="cleanup suggest")


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
