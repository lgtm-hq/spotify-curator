"""Playlist service helpers."""

from __future__ import annotations

from typing import Any

import spotipy

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
    for item in items:
        playlists.append(_summary_from_meta(item, current_user_id=current_user_id))
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
