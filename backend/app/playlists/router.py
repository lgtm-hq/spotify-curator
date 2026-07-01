"""Playlist API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.router import get_current_user, get_db
from app.playlists.models import PlaylistDetail, PlaylistSummary
from app.playlists.service import get_playlist, list_playlists
from app.spotify_client import get_spotify_client

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.get("", response_model=list[PlaylistSummary])
async def get_playlists(
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PlaylistSummary]:
    """List all user playlists."""
    sp = await get_spotify_client(db)
    return list_playlists(sp)


@router.get("/{playlist_id}", response_model=PlaylistDetail)
async def get_playlist_detail(
    playlist_id: str,
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlaylistDetail:
    """Get playlist with tracks."""
    sp = await get_spotify_client(db)
    return get_playlist(sp, playlist_id=playlist_id)
