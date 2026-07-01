"""Taste profile models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TasteProfile(BaseModel):
    """Structured taste profile."""

    summary: str = ""
    genres: list[str] = Field(default_factory=list)
    mood_tags: list[str] = Field(default_factory=list)
    era_preference: str = ""
    energy_range: str = ""
    top_artist_ids: list[str] = Field(default_factory=list)
    top_track_ids: list[str] = Field(default_factory=list)
    seed_genres: list[str] = Field(default_factory=list)
