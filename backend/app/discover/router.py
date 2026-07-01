"""Discover API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.router import get_current_user, get_db
from app.db import DiscoverRunRecord
from app.discover.service import generate_discovery_playlist
from app.spotify_client import get_spotify_client

router = APIRouter(prefix="/discover", tags=["discover"])


@router.post("/generate")
async def discover_generate(
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate discovery playlist on demand."""
    sp = await get_spotify_client(db)
    return generate_discovery_playlist(sp, db=db)


@router.get("/history")
async def discover_history(
    _user: str = Depends(get_current_user),
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
            "run_id": r.id,
            "playlist_id": r.playlist_id,
            "name": r.playlist_name,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]
