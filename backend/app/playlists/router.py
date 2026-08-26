"""Playlist API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from spotipy.exceptions import SpotifyException
from sqlalchemy.orm import Session

from app.auth.router import get_current_user, get_db
from app.auth.user import get_user_by_spotify_id
from app.cleanup.playlist_scan import (
    load_all_cached_stats,
    refresh_owned_playlist_scans,
)
from app.db import SessionLocal, TokenRecord, User
from app.playlists.cache import (
    load_playlist_list_cache,
    normalize_playlists_for_user,
    patch_playlist_in_cache,
    playlist_cache_updated_at,
    playlists_from_scan_cache,
    purge_playlist_local_references,
    repair_playlist_list_cache,
    save_playlist_list_cache,
)
from app.playlists.curated_sources import curated_playlist_sources
from app.playlists.models import (
    CuratedPlaylistSource,
    PlaylistDetail,
    PlaylistsResponse,
    PlaylistSummary,
    SpotifyUsageStatus,
)
from app.playlists.service import (
    can_edit_from_list_cache,
    can_edit_from_metadata,
    get_playlist,
    list_playlists,
    remove_tracks,
    remove_tracks_by_uri,
    reorder_tracks,
    unfollow_playlist,
    update_playlist_metadata,
)
from app.spotify_client import call_spotify, get_spotify_client, get_spotify_client_sync
from app.spotify_usage import (
    record_rate_limit,
    record_spotify_request,
    retry_after_from_exception,
    usage_status,
)

router = APIRouter(prefix="/playlists", tags=["playlists"])
logger = logging.getLogger(__name__)


class RemoveTracksRequest(BaseModel):
    """Request to remove tracks from a playlist."""

    track_ids: list[str] = Field(default_factory=list)
    track_uris: list[str] = Field(default_factory=list)


class ReorderTracksRequest(BaseModel):
    """Request to reorder tracks within a playlist."""

    range_start: int
    insert_before: int
    range_length: int = 1


class UpdatePlaylistRequest(BaseModel):
    """Request to update playlist metadata."""

    name: str | None = None
    description: str | None = None
    public: bool | None = None


def _playlist_http_error(exc: Exception, *, action: str) -> HTTPException:
    """Translate playlist failures into HTTP errors."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, SpotifyException):
        logger.error("Spotify error during playlist %s: %s", action, exc)
        if exc.http_status == 429:
            return HTTPException(
                status_code=429,
                detail="Spotify rate limit reached. Try again later.",
            )
        if exc.http_status == 403:
            return HTTPException(
                status_code=403,
                detail="Spotify denied access to this playlist.",
            )
        if exc.http_status == 404:
            return HTTPException(
                status_code=404,
                detail="Playlist not found.",
            )
        return HTTPException(
            status_code=502,
            detail="Spotify couldn't complete that request.",
        )
    if isinstance(exc, PydanticValidationError):
        logger.exception("Playlist %s response validation failed", action)
        return HTTPException(
            status_code=500, detail="Invalid playlist data from Spotify"
        )
    logger.exception("Playlist %s failed", action)
    return HTTPException(status_code=500, detail="Failed to load playlist")


def _curated_sources_for_response(db: Session) -> dict[str, CuratedPlaylistSource]:
    sources = curated_playlist_sources(db)
    return {
        playlist_id: CuratedPlaylistSource.model_validate(meta)
        for playlist_id, meta in sources.items()
    }


def _build_playlists_response(db: Session, *, user: User) -> PlaylistsResponse:
    """Return cached playlists and current Spotify usage metadata."""
    cached = repair_playlist_list_cache(
        db,
        current_user_id=user.spotify_id,
        current_user_display_name=user.display_name,
    )
    if cached is None:
        cached = playlists_from_scan_cache(db) or []
    if cached:
        cached = normalize_playlists_for_user(
            cached,
            current_user_id=user.spotify_id,
            current_user_display_name=user.display_name,
        )
    last_fetched = playlist_cache_updated_at(db)
    usage = usage_status(db, last_fetched_at=last_fetched)
    message: str | None = None
    if not cached:
        message = "No saved playlists yet. Refresh from Spotify to load your library."
    elif load_playlist_list_cache(db) is None and playlists_from_scan_cache(db):
        message = "Showing playlists rebuilt from cleanup scan cache."
    sources = _curated_sources_for_response(db)
    return PlaylistsResponse(
        playlists=cached,
        last_fetched_at=usage["last_fetched_at"],
        from_cache=True,
        cache_message=message,
        spotify_usage=SpotifyUsageStatus.model_validate(usage),
        curated_sources=sources,
    )


@router.get("/usage", response_model=SpotifyUsageStatus)
async def get_spotify_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpotifyUsageStatus:
    """Return live Spotify API usage and rate-limit state for global UI."""
    del current_user
    usage = usage_status(db, last_fetched_at=playlist_cache_updated_at(db))
    return SpotifyUsageStatus.model_validate(usage)


@router.get("", response_model=PlaylistsResponse)
async def get_playlists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlaylistsResponse:
    """Return cached playlists without calling Spotify."""
    return _build_playlists_response(db, user=current_user)


@router.post("/refresh", response_model=PlaylistsResponse)
async def refresh_playlists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlaylistsResponse:
    """Fetch playlists from Spotify and update the local cache."""
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

    try:
        sp = await get_spotify_client(db)
        playlists = await call_spotify(
            list_playlists,
            sp,
            current_user_id=current_user.spotify_id,
        )
        playlists = normalize_playlists_for_user(
            playlists,
            current_user_id=current_user.spotify_id,
            current_user_display_name=current_user.display_name,
        )
        save_playlist_list_cache(db, playlists)
        page_estimate = max(1, (len(playlists) + 49) // 50)
        record_spotify_request(db, count=page_estimate)
        last_fetched = playlist_cache_updated_at(db)
        fresh_usage = usage_status(db, last_fetched_at=last_fetched)
        return PlaylistsResponse(
            playlists=playlists,
            last_fetched_at=fresh_usage["last_fetched_at"],
            from_cache=False,
            cache_message=None,
            spotify_usage=SpotifyUsageStatus.model_validate(fresh_usage),
            curated_sources=_curated_sources_for_response(db),
        )
    except SpotifyException as exc:
        record_spotify_request(db, count=1)
        if exc.http_status == 429:
            record_rate_limit(db, retry_after_seconds=retry_after_from_exception(exc))
        cached = load_playlist_list_cache(db) or playlists_from_scan_cache(db) or []
        last_fetched = playlist_cache_updated_at(db)
        fresh_usage = usage_status(db, last_fetched_at=last_fetched)
        detail = "Spotify rate limit reached."
        if fresh_usage["seconds_until_reset"] is not None:
            detail = (
                f"Spotify rate limit reached. Try again in "
                f"{fresh_usage['seconds_until_reset']} seconds."
            )
        if cached:
            return PlaylistsResponse(
                playlists=cached,
                last_fetched_at=fresh_usage["last_fetched_at"],
                from_cache=True,
                cache_message=detail,
                spotify_usage=SpotifyUsageStatus.model_validate(fresh_usage),
                curated_sources=_curated_sources_for_response(db),
            )
        raise HTTPException(status_code=429, detail=detail) from exc


@router.get("/scan-summaries")
async def get_scan_summaries(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, object]]:
    """Return cached cleanup scan stats keyed by playlist id."""
    return load_all_cached_stats(db)


def _run_scan_refresh(current_user_id: str) -> None:
    db = SessionLocal()
    try:
        user = get_user_by_spotify_id(db, spotify_id=current_user_id)
        sp = get_spotify_client_sync(db)
        cached_playlists = repair_playlist_list_cache(
            db,
            current_user_id=current_user_id,
            current_user_display_name=user.display_name if user else None,
        )
        if cached_playlists is None:
            cached_playlists = list_playlists(sp, current_user_id=current_user_id)
        else:
            cached_playlists = normalize_playlists_for_user(
                cached_playlists,
                current_user_id=current_user_id,
                current_user_display_name=user.display_name if user else None,
            )
        refresh_owned_playlist_scans(
            sp,
            db,
            current_user_id=current_user_id,
            playlists=cached_playlists,
            current_user_display_name=user.display_name if user else None,
        )
    except Exception:
        logger.exception("Background playlist scan refresh failed")
    finally:
        db.close()


@router.post("/scan-summaries/refresh")
async def refresh_scan_summaries(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Background refresh of cleanup stats for all owned playlists."""
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
    token = db.get(TokenRecord, 1)
    if token is None:
        raise HTTPException(status_code=401, detail="Spotify not connected")
    background_tasks.add_task(_run_scan_refresh, current_user.spotify_id)
    return {"status": "scanning"}


async def _ensure_can_edit(
    db: Session,
    sp: object,
    *,
    playlist_id: str,
    user_id: str,
) -> None:
    """Verify the user may edit a playlist without loading all tracks."""
    cached = can_edit_from_list_cache(db, playlist_id=playlist_id)
    if cached is not None:
        if not cached:
            raise HTTPException(status_code=403, detail="You cannot edit this playlist")
        return
    allowed = await call_spotify(
        can_edit_from_metadata,
        sp,
        playlist_id=playlist_id,
        current_user_id=user_id,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="You cannot edit this playlist")


@router.get("/{playlist_id}", response_model=PlaylistDetail)
async def get_playlist_detail(
    playlist_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlaylistDetail:
    """Get playlist with tracks."""
    try:
        sp = await get_spotify_client(db)
        detail = await call_spotify(
            get_playlist,
            sp,
            playlist_id=playlist_id,
            current_user_id=current_user.spotify_id,
        )
        record_spotify_request(db, count=max(1, (len(detail.tracks) + 49) // 50 + 1))
        return detail
    except SpotifyException as exc:
        record_spotify_request(db, count=1)
        if exc.http_status == 429:
            record_rate_limit(db, retry_after_seconds=retry_after_from_exception(exc))
        raise _playlist_http_error(exc, action="load") from exc
    except Exception as exc:
        raise _playlist_http_error(exc, action="load") from exc


@router.post("/{playlist_id}/tracks/remove")
async def remove_playlist_tracks(
    playlist_id: str,
    body: RemoveTracksRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Remove tracks from a playlist."""
    sp = await get_spotify_client(db)
    await _ensure_can_edit(
        db,
        sp,
        playlist_id=playlist_id,
        user_id=current_user.spotify_id,
    )
    if body.track_uris:
        removed = await call_spotify(
            remove_tracks_by_uri,
            sp,
            playlist_id=playlist_id,
            track_uris=body.track_uris,
        )
    else:
        removed = await call_spotify(
            remove_tracks,
            sp,
            playlist_id=playlist_id,
            track_ids=body.track_ids,
        )
    record_spotify_request(db, count=1 if body.track_uris else max(2, 1))
    return {"removed": removed}


@router.post("/{playlist_id}/tracks/reorder")
async def reorder_playlist_tracks(
    playlist_id: str,
    body: ReorderTracksRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Reorder tracks within a playlist."""
    sp = await get_spotify_client(db)
    await _ensure_can_edit(
        db,
        sp,
        playlist_id=playlist_id,
        user_id=current_user.spotify_id,
    )
    await call_spotify(
        reorder_tracks,
        sp,
        playlist_id=playlist_id,
        range_start=body.range_start,
        insert_before=body.insert_before,
        range_length=body.range_length,
    )
    record_spotify_request(db, count=1)
    return {"status": "ok"}


@router.patch("/{playlist_id}", response_model=PlaylistSummary)
async def update_playlist(
    playlist_id: str,
    body: UpdatePlaylistRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlaylistSummary:
    """Update playlist name, description, or visibility."""
    if body.name is None and body.description is None and body.public is None:
        raise HTTPException(status_code=400, detail="No playlist fields to update.")
    try:
        sp = await get_spotify_client(db)
        await _ensure_can_edit(
            db,
            sp,
            playlist_id=playlist_id,
            user_id=current_user.spotify_id,
        )
        updated = await call_spotify(
            update_playlist_metadata,
            sp,
            playlist_id=playlist_id,
            current_user_id=current_user.spotify_id,
            name=body.name,
            description=body.description,
            public=body.public,
        )
        record_spotify_request(db, count=2)
        patch_playlist_in_cache(db, updated)
        return updated
    except SpotifyException as exc:
        record_spotify_request(db, count=1)
        if exc.http_status == 429:
            record_rate_limit(db, retry_after_seconds=retry_after_from_exception(exc))
        raise _playlist_http_error(exc, action="update") from exc
    except Exception as exc:
        raise _playlist_http_error(exc, action="update") from exc


@router.delete("/{playlist_id}")
async def delete_playlist(
    playlist_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Remove a playlist from the user's Spotify library."""
    try:
        sp = await get_spotify_client(db)
        await _ensure_can_edit(
            db,
            sp,
            playlist_id=playlist_id,
            user_id=current_user.spotify_id,
        )
        await call_spotify(unfollow_playlist, sp, playlist_id=playlist_id)
        record_spotify_request(db, count=1)
        purge_playlist_local_references(db, playlist_id=playlist_id)
        return {"status": "deleted"}
    except SpotifyException as exc:
        record_spotify_request(db, count=1)
        if exc.http_status == 429:
            record_rate_limit(db, retry_after_seconds=retry_after_from_exception(exc))
        raise _playlist_http_error(exc, action="delete") from exc
    except Exception as exc:
        raise _playlist_http_error(exc, action="delete") from exc
