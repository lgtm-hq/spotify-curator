"""Configuration for AI cleanup library scans."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

FocusArea = Literal["duplicates", "unavailable", "bloated"]
ALL_FOCUS_AREAS: list[FocusArea] = ["duplicates", "unavailable", "bloated"]


class CleanupSuggestOptions(BaseModel):
    """User-configurable options for an AI cleanup advisor run."""

    scope: Literal["all_owned", "selected", "all_in_library"] = "all_owned"
    playlist_ids: list[str] = Field(default_factory=list)
    exclude_playlist_ids: list[str] = Field(default_factory=list)
    user_prompt: str | None = Field(default=None, max_length=2000)
    use_scan_cache: bool = True
    force_rescan: bool = False
    min_track_count: int = Field(default=1, ge=0)
    focus_areas: list[FocusArea] = Field(default_factory=lambda: list(ALL_FOCUS_AREAS))
    conservative_scan: bool = False
    sort_by: Literal[
        "track_count_desc",
        "track_count_asc",
        "name_asc",
        "name_desc",
        "stale_first",
        "recently_scanned",
    ] = "track_count_desc"
    stale_after_days: int | None = Field(default=None, ge=1, le=365)
    min_duplicates: int = Field(default=0, ge=0)
    min_unavailable: int = Field(default=0, ge=0)
    min_bloated_tracks: int = Field(default=150, ge=50)
    include_taste_profile: bool = True
    custom_taste_summary: str | None = Field(default=None, max_length=2000)
    quick_start_id: str | None = Field(default="full-audit", max_length=64)

    @model_validator(mode="before")
    @classmethod
    def coerce_legacy_focus(cls, data: Any) -> Any:
        """Map deprecated single ``focus`` field to ``focus_areas``."""
        if not isinstance(data, dict):
            return data
        if "focus_areas" not in data and "focus" in data:
            legacy = data.pop("focus")
            if legacy in (None, "all"):
                data["focus_areas"] = list(ALL_FOCUS_AREAS)
            else:
                data["focus_areas"] = [legacy]
        return data

    def resolved_focus_areas(self) -> list[FocusArea]:
        """Return normalized focus areas; empty selection means all."""
        if not self.focus_areas:
            return list(ALL_FOCUS_AREAS)
        return list(self.focus_areas)

    def effective_use_cache(self) -> bool:
        """Return whether scan steps may read cached playlist stats."""
        return self.use_scan_cache and not self.force_rescan
