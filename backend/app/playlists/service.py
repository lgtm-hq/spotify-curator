"""Playlist service helpers."""

from __future__ import annotations

from typing import Any

import spotipy
from sqlalchemy.orm import Session

from app.playlists.models import (
    PlaylistDetail,
    PlaylistSummary,
    TrackArtist,
    TrackSummary,
)
from app.spotify_client import (
    paginate,
    paginate_playlist_items,
    paginate_playlist_items_lite,
    playlist_entry_track,
    playlist_track_total,
)


def _map_track(item: dict[str, Any]) -> TrackSummary | None:
    """Map Spotify playlist track item to TrackSummary."""
    track = playlist_entry_track(item) or item
    if (
        not isinstance(track, dict)
        or track.get("type") != "track"
        or not track.get("id")
    ):
        return None
    artists = [
        TrackArtist(id=a.get("id"), name=str(a.get("name") or "Unknown"))
        for a in track.get("artists", [])
    ]
    album = track.get("album") or {}
    images = album.get("images") or []
    return TrackSummary(
        id=str(track["id"]),
        name=str(track.get("name") or "Unknown"),
        artists=artists,
        uri=str(track.get("uri") or f"spotify:track:{track['id']}"),
        is_playable=track.get("is_playable") is not False,
        album=album.get("name"),
        album_image_url=images[-1]["url"] if images else None,
        duration_ms=int(track.get("duration_ms") or 0),
    )


def _summary_from_meta(
    meta: dict[str, Any],
    *,
    current_user_id: str | None = None,
) -> PlaylistSummary:
    """Build playlist summary from Spotify metadata."""
    images = meta.get("images") or []
    owner = meta.get("owner") or {}
    owner_id = str(owner.get("id", ""))
    return PlaylistSummary(
        id=str(meta["id"]),
        name=str(meta.get("name") or "Untitled"),
        description=meta.get("description") or None,
        owner=str(owner.get("display_name") or owner.get("id") or "Unknown"),
        owner_id=owner_id,
        track_count=playlist_track_total(meta),
        image_url=images[0]["url"] if images else None,
        public=bool(meta.get("public", False)),
        can_edit=bool(current_user_id and owner_id == current_user_id),
    )


def list_playlists(
    sp: spotipy.Spotify,
    *,
    current_user_id: str | None = None,
) -> list[PlaylistSummary]:
    """Fetch all user playlists."""
    items = paginate(sp, "current_user_playlists")
    playlists: list[PlaylistSummary] = []
    for index, item in enumerate(items):
        summary = _summary_from_meta(item, current_user_id=current_user_id)
        playlists.append(summary.model_copy(update={"library_order": index}))
    return playlists


def fetch_playlist_tracks_lite(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
    max_tracks: int = 100,
) -> list[TrackSummary]:
    """Fetch a capped sample of playlist tracks for quick analysis."""
    items = paginate_playlist_items_lite(
        sp,
        playlist_id=playlist_id,
        max_items=max_tracks,
    )
    tracks: list[TrackSummary] = []
    for item in items:
        mapped = _map_track(item)
        if mapped:
            tracks.append(mapped)
    return tracks


def get_playlist(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
    current_user_id: str | None = None,
) -> PlaylistDetail:
    """Fetch playlist with all tracks."""
    meta = sp.playlist(playlist_id)
    track_items = paginate_playlist_items(sp, playlist_id=playlist_id)
    tracks: list[TrackSummary] = []
    for item in track_items:
        mapped = _map_track(item)
        if mapped:
            tracks.append(mapped)
    summary = _summary_from_meta(meta, current_user_id=current_user_id)
    return PlaylistDetail(
        **summary.model_dump(exclude={"track_count"}),
        track_count=summary.track_count or len(tracks),
        tracks=tracks,
    )


def remove_tracks(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
    track_ids: list[str],
) -> int:
    """Remove tracks from a playlist by Spotify track ID."""
    if not track_ids:
        return 0

    items = paginate_playlist_items(sp, playlist_id=playlist_id)
    remove_ids = set(track_ids)
    uris = [
        track["uri"]
        for entry in items
        if (track := playlist_entry_track(entry)) and track.get("id") in remove_ids
    ]
    if uris:
        sp.playlist_remove_all_occurrences_of_items(playlist_id, uris)
    return len(uris)


def reorder_tracks(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
    range_start: int,
    insert_before: int,
    range_length: int = 1,
) -> None:
    """Reorder tracks within a playlist."""
    sp.playlist_reorder_items(
        playlist_id,
        range_start,
        insert_before,
        range_length=range_length,
    )


def remove_tracks_by_uri(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
    track_uris: list[str],
) -> int:
    """Remove tracks from a playlist using known Spotify URIs."""
    if not track_uris:
        return 0
    sp.playlist_remove_all_occurrences_of_items(playlist_id, track_uris)
    return len(track_uris)


def update_playlist_metadata(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
    current_user_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
    public: bool | None = None,
) -> PlaylistSummary:
    """Update playlist name, description, or visibility."""
    changes: dict[str, object] = {}
    if name is not None:
        changes["name"] = name.strip() or "Untitled"
    if description is not None:
        changes["description"] = description
    if public is not None:
        changes["public"] = public
    if changes:
        sp.playlist_change_details(playlist_id, **changes)
    meta = sp.playlist(playlist_id)
    return _summary_from_meta(meta, current_user_id=current_user_id)


def unfollow_playlist(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
) -> None:
    """Remove a playlist from the user's library."""
    sp.current_user_unfollow_playlist(playlist_id)


def can_edit_from_list_cache(
    db: Session,
    *,
    playlist_id: str,
) -> bool | None:
    """Return edit permission from cached playlist list, if known."""
    from app.playlists.cache import load_playlist_list_cache, playlists_from_scan_cache

    for source in (load_playlist_list_cache(db), playlists_from_scan_cache(db)):
        if not source:
            continue
        for playlist in source:
            if playlist.id == playlist_id:
                return playlist.can_edit
    return None


def can_edit_from_metadata(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
    current_user_id: str,
) -> bool:
    """Check edit permission with a single playlist metadata request."""
    meta = sp.playlist(playlist_id)
    owner = meta.get("owner") or {}
    return str(owner.get("id", "")) == current_user_id
