"""Playlist Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TrackArtist(BaseModel):
    """Track artist summary."""

    id: str | None = None
    name: str


class TrackSummary(BaseModel):
    """Minimal track representation."""

    id: str
    name: str
    artists: list[TrackArtist] = Field(default_factory=list)
    uri: str
    is_playable: bool = True
    album: str | None = None
    album_image_url: str | None = None
    duration_ms: int = 0


class PlaylistSummary(BaseModel):
    """Minimal playlist representation."""

    id: str
    name: str
    description: str | None = None
    owner: str
    owner_id: str = ""
    track_count: int
    image_url: str | None = None
    public: bool = False
    can_edit: bool = False
    library_order: int = 0


class PlaylistDetail(PlaylistSummary):
    """Playlist with tracks."""

    tracks: list[TrackSummary] = Field(default_factory=list)


class SpotifyUsageStatus(BaseModel):
    """Spotify API usage snapshot for dashboard UI."""

    state: str
    requests_in_window: int
    window_seconds: int
    estimated_limit: int
    usage_percent: int
    rate_limited_until: str | None = None
    seconds_until_reset: int | None = None
    last_fetched_at: str | None = None


class PlaylistsResponse(BaseModel):
    """Playlist list with cache and Spotify usage metadata."""

    playlists: list[PlaylistSummary]
    last_fetched_at: str | None = None
    from_cache: bool = True
    cache_message: str | None = None
    spotify_usage: SpotifyUsageStatus | None = None
    curated_sources: dict[str, CuratedPlaylistSource] = Field(default_factory=dict)


class CuratedPlaylistSource(BaseModel):
    """App-generated playlist metadata for dashboard grouping."""

    source: str
    label: str
    created_at: str | None = None
