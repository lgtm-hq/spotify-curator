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
from app.spotify_client import paginate, playlist_entry_track, playlist_track_total


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
        TrackArtist(id=a.get("id"), name=a.get("name", "Unknown"))
        for a in track.get("artists", [])
    ]
    return TrackSummary(
        id=track["id"],
        name=track.get("name", "Unknown"),
        artists=artists,
        uri=track.get("uri", f"spotify:track:{track['id']}"),
        is_playable=track.get("is_playable", True),
        album=(track.get("album") or {}).get("name"),
        duration_ms=track.get("duration_ms", 0),
    )


def list_playlists(sp: spotipy.Spotify) -> list[PlaylistSummary]:
    """Fetch all user playlists."""
    items = paginate(sp, "current_user_playlists")
    playlists: list[PlaylistSummary] = []
    for item in items:
        images = item.get("images") or []
        playlists.append(
            PlaylistSummary(
                id=item["id"],
                name=item.get("name", "Untitled"),
                description=item.get("description"),
                owner=(item.get("owner") or {}).get("display_name", "Unknown"),
                track_count=playlist_track_total(item),
                image_url=images[0]["url"] if images else None,
                public=item.get("public", False),
            ),
        )
    return playlists


def get_playlist(sp: spotipy.Spotify, *, playlist_id: str) -> PlaylistDetail:
    """Fetch playlist with all tracks."""
    meta = sp.playlist(playlist_id)
    track_items = paginate(sp, "playlist_items", playlist_id=playlist_id)
    tracks: list[TrackSummary] = []
    for item in track_items:
        mapped = _map_track(item)
        if mapped:
            tracks.append(mapped)
    images = meta.get("images") or []
    return PlaylistDetail(
        id=meta["id"],
        name=meta.get("name", "Untitled"),
        description=meta.get("description"),
        owner=(meta.get("owner") or {}).get("display_name", "Unknown"),
        track_count=playlist_track_total(meta) or len(tracks),
        image_url=images[0]["url"] if images else None,
        public=meta.get("public", False),
        tracks=tracks,
    )
