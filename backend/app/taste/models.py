"""Taste profile models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TasteLane(BaseModel):
    """A distinct listening lane within the user's taste."""

    label: str = ""
    description: str = ""
    artists: list[str] = Field(default_factory=list)


class TasteProfile(BaseModel):
    """Structured taste profile."""

    summary: str = ""
    genres: list[str] = Field(default_factory=list)
    mood_tags: list[str] = Field(default_factory=list)
    era_preference: str = ""
    energy_range: str = ""
    taste_lanes: list[TasteLane] = Field(default_factory=list)
    core_taste: str = ""
    recent_shift: str = ""
    curation_hints: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    audio_features_summary: str = ""
    top_artist_ids: list[str] = Field(default_factory=list)
    top_track_ids: list[str] = Field(default_factory=list)
    seed_genres: list[str] = Field(default_factory=list)
