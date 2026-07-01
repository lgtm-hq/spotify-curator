"""Playlist API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session
from spotipy.exceptions import SpotifyException

from app.auth.router import get_current_user, get_db
from app.playlists.models import PlaylistDetail, PlaylistSummary
from app.playlists.service import (
    get_playlist,
    list_playlists,
    remove_tracks,
    reorder_tracks,
)
from app.spotify_client import get_spotify_client

router = APIRouter(prefix="/playlists", tags=["playlists"])
logger = logging.getLogger(__name__)


class RemoveTracksRequest(BaseModel):
    """Request to remove tracks from a playlist."""

    track_ids: list[str] = Field(default_factory=list)


class ReorderTracksRequest(BaseModel):
    """Request to reorder tracks within a playlist."""

    range_start: int
    insert_before: int
    range_length: int = 1


def _playlist_http_error(exc: Exception, *, action: str) -> HTTPException:
    """Translate playlist failures into HTTP errors."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, SpotifyException):
        logger.error("Spotify error during playlist %s: %s", action, exc)
        return HTTPException(status_code=502, detail=f"Spotify API error: {exc}")
    if isinstance(exc, PydanticValidationError):
        logger.exception("Playlist %s response validation failed", action)
        return HTTPException(status_code=500, detail="Invalid playlist data from Spotify")
    logger.exception("Playlist %s failed", action)
    return HTTPException(status_code=500, detail="Failed to load playlist")


@router.get("", response_model=list[PlaylistSummary])
async def get_playlists(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PlaylistSummary]:
    """List all user playlists."""
    sp = await get_spotify_client(db)
    return list_playlists(sp, current_user_id=user_id)


@router.get("/{playlist_id}", response_model=PlaylistDetail)
async def get_playlist_detail(
    playlist_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlaylistDetail:
    """Get playlist with tracks."""
    try:
        sp = await get_spotify_client(db)
        return get_playlist(sp, playlist_id=playlist_id, current_user_id=user_id)
    except Exception as exc:
        raise _playlist_http_error(exc, action="load") from exc


@router.post("/{playlist_id}/tracks/remove")
async def remove_playlist_tracks(
    playlist_id: str,
    body: RemoveTracksRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Remove tracks from a playlist."""
    sp = await get_spotify_client(db)
    detail = get_playlist(sp, playlist_id=playlist_id, current_user_id=user_id)
    if not detail.can_edit:
        raise HTTPException(status_code=403, detail="You cannot edit this playlist")
    removed = remove_tracks(sp, playlist_id=playlist_id, track_ids=body.track_ids)
    return {"removed": removed}


@router.post("/{playlist_id}/tracks/reorder")
async def reorder_playlist_tracks(
    playlist_id: str,
    body: ReorderTracksRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Reorder tracks within a playlist."""
    sp = await get_spotify_client(db)
    detail = get_playlist(sp, playlist_id=playlist_id, current_user_id=user_id)
    if not detail.can_edit:
        raise HTTPException(status_code=403, detail="You cannot edit this playlist")
    reorder_tracks(
        sp,
        playlist_id=playlist_id,
        range_start=body.range_start,
        insert_before=body.insert_before,
        range_length=body.range_length,
    )
    return {"status": "ok"}
