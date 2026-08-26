"""Unit tests for deterministic taste engine helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from assertpy import assert_that

from app.taste.engine import (
    _avg_features,
    _fallback_profile,
    _profile_from_ai,
    _release_year_summary,
    compact_taste_for_prompt,
)


def _taste_data(*, audio_features_available: bool = True) -> dict[str, Any]:
    """Build minimal listening data for profile construction tests."""
    return {
        "seed_genres": ["indie", "dream pop", "ambient"],
        "top_artist_ids": ["artist-1", "artist-2", "artist-3"],
        "top_track_ids": ["track-1", "track-2", "track-3"],
        "audio_features_available": audio_features_available,
    }


def test_avg_features_batches_tracks_and_rounds_scores() -> None:
    """Verify average feature scoring uses all successful feature rows."""
    feature_pages: list[list[dict[str, Any] | None]] = [
        [
            {
                "energy": 0.2,
                "valence": 0.8,
                "danceability": 0.4,
                "tempo": 90.0,
                "acousticness": 0.1,
                "instrumentalness": 0.0,
                "speechiness": 0.05,
            },
            {
                "energy": 0.7,
                "valence": 0.4,
                "danceability": 0.8,
                "tempo": 120.1234,
                "acousticness": 0.3,
                "instrumentalness": 0.2,
                "speechiness": 0.15,
            },
        ],
        [None],
    ]
    calls: list[list[str]] = []

    def audio_features(batch: list[str]) -> list[dict[str, Any] | None]:
        """Return one configured feature page per requested batch."""
        calls.append(batch)
        return feature_pages.pop(0)

    features, available = _avg_features(
        SimpleNamespace(audio_features=audio_features),
        [f"track-{index}" for index in range(101)],
    )

    assert_that(available).is_true()
    assert_that([len(batch) for batch in calls]).is_equal_to([100, 1])
    assert_that(features).contains_entry({"energy": 0.45})
    assert_that(features).contains_entry({"valence": 0.6})
    assert_that(features).contains_entry({"danceability": 0.6})
    assert_that(features).contains_entry({"tempo": 105.062})
    assert_that(features).contains_entry({"speechiness": 0.1})


def test_avg_features_reports_unavailable_when_batches_fail() -> None:
    """Verify failed audio-feature batches produce an unavailable score."""

    def audio_features(_batch: list[str]) -> list[dict[str, Any]]:
        """Simulate Spotify audio-feature failures."""
        raise RuntimeError("spotify unavailable")

    features, available = _avg_features(
        SimpleNamespace(audio_features=audio_features),
        ["track-1"],
    )

    assert_that(available).is_false()
    assert_that(features).is_empty()


@pytest.mark.parametrize(
    ("tracks", "expected"),
    [
        pytest.param([], {}, id="empty"),
        pytest.param([{"year": "1999"}], {}, id="non-integer-year"),
        pytest.param(
            [{"year": 1990}, {"year": 2010}, {"year": 2000}],
            {"min": 1990, "max": 2010, "median": 2000, "sample_size": 3},
            id="odd-sample",
        ),
        pytest.param(
            [{"year": 1990}, {"year": 2020}],
            {"min": 1990, "max": 2020, "median": 2005, "sample_size": 2},
            id="even-sample",
        ),
    ],
)
def test_release_year_summary_handles_edges(
    tracks: list[dict[str, Any]],
    expected: dict[str, int],
) -> None:
    """Verify release-year summary scoring handles sparse samples."""
    assert_that(_release_year_summary(tracks)).is_equal_to(expected)


def test_profile_from_ai_normalizes_synthetic_profile_scores() -> None:
    """Verify AI profile data is bounded before it reaches scoring prompts."""
    parsed = {
        "summary": "  " + ("warm " * 200),
        "genres": [],
        "mood_tags": ["focused", "", "late night", "driving", "coding", "soft", "x"],
        "era_preference": "  2000s  ",
        "energy_range": "medium",
        "taste_lanes": [
            {
                "label": f"Lane {index}",
                "description": "Synthetic lane",
                "artists": [f"Artist {artist}" for artist in range(7)],
            }
            for index in range(5)
        ],
        "core_taste": "melodic",
        "recent_shift": "brighter",
        "curation_hints": [f"hint-{index}" for index in range(7)],
        "avoid": [f"avoid-{index}" for index in range(8)],
        "confidence": "unexpected",
        "audio_features_summary": "balanced",
    }

    profile = _profile_from_ai(parsed, _taste_data())

    assert_that(len(profile.summary)).is_less_than_or_equal_to(600)
    assert_that(profile.summary).ends_with("\u2026")
    assert_that(profile.genres).is_equal_to(["indie", "dream pop", "ambient"])
    assert_that(profile.mood_tags).is_equal_to(
        ["focused", "late night", "driving", "coding", "soft", "x"],
    )
    assert_that(profile.era_preference).is_equal_to("2000s")
    assert_that(profile.taste_lanes).is_length(4)
    assert_that(profile.taste_lanes[0].artists).is_length(5)
    assert_that(profile.curation_hints).is_length(5)
    assert_that(profile.avoid).is_length(6)
    assert_that(profile.confidence).is_equal_to("medium")
    assert_that(profile.top_artist_ids).is_equal_to(
        ["artist-1", "artist-2", "artist-3"]
    )
    assert_that(profile.top_track_ids).is_equal_to(
        ["track-1", "track-2", "track-3"],
    )


@pytest.mark.parametrize(
    ("audio_features_available", "expected_summary"),
    [
        pytest.param(
            True,
            "Audio features were averaged from medium-term top tracks.",
            id="audio-features-available",
        ),
        pytest.param(
            False,
            "Audio feature data was unavailable from Spotify.",
            id="audio-features-unavailable",
        ),
    ],
)
def test_fallback_profile_scores_audio_feature_availability(
    audio_features_available: bool,
    expected_summary: str,
) -> None:
    """Verify fallback profiles describe whether feature scoring was available."""
    profile = _fallback_profile(
        _taste_data(audio_features_available=audio_features_available),
    )

    assert_that(profile.confidence).is_equal_to("low")
    assert_that(profile.audio_features_summary).is_equal_to(expected_summary)
    assert_that(profile.genres).is_equal_to(["indie", "dream pop", "ambient"])


def test_compact_taste_for_prompt_limits_scoring_payload() -> None:
    """Verify prompt payloads keep only the top bounded scoring inputs."""
    profile = _profile_from_ai(
        {
            "summary": "Synthetic summary",
            "genres": [f"genre-{index}" for index in range(12)],
            "mood_tags": [f"mood-{index}" for index in range(8)],
            "taste_lanes": [
                {
                    "label": f"Lane {index}",
                    "description": "Description",
                    "artists": [f"Artist {artist}" for artist in range(7)],
                }
                for index in range(5)
            ],
            "curation_hints": [f"hint-{index}" for index in range(7)],
            "avoid": [f"avoid-{index}" for index in range(8)],
            "confidence": "high",
        },
        _taste_data(),
    )

    payload = json.loads(compact_taste_for_prompt(profile))

    assert_that(payload["genres"]).is_length(8)
    assert_that(payload["mood_tags"]).is_length(6)
    assert_that(payload["taste_lanes"]).is_length(4)
    assert_that(payload["taste_lanes"][0]["artists"]).is_length(5)
    assert_that(payload["curation_hints"]).is_length(5)
    assert_that(payload["avoid"]).is_length(6)
