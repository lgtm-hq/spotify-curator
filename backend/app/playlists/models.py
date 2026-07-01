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
    duration_ms: int = 0


class PlaylistSummary(BaseModel):
    """Minimal playlist representation."""

    id: str
    name: str
    description: str | None = None
    owner: str
    track_count: int
    image_url: str | None = None
    public: bool = False


class PlaylistDetail(PlaylistSummary):
    """Playlist with tracks."""

    tracks: list[TrackSummary] = Field(default_factory=list)
