"""Unit tests for cleanup advisor suggestion helpers."""

from __future__ import annotations

import pytest
from assertpy import assert_that

from app.cleanup.suggest_jobs import _focus_hint_for_areas, _heuristic_suggestions
from app.cleanup.suggest_options import ALL_FOCUS_AREAS, CleanupSuggestOptions


def _scan(
    *,
    duplicate_tracks: int = 0,
    unavailable_tracks: int = 0,
    track_count: int = 25,
) -> dict[str, object]:
    """Build a scan payload for heuristic suggestion tests."""
    return {
        "playlist_id": "playlist-1",
        "playlist_name": "Road Trip",
        "duplicate_tracks": duplicate_tracks,
        "unavailable_tracks": unavailable_tracks,
        "track_count": track_count,
    }


@pytest.mark.parametrize(
    ("focus_areas", "expected_fragments"),
    [
        pytest.param(ALL_FOCUS_AREAS, [], id="all-areas"),
        pytest.param(
            ["duplicates"],
            ["duplicate tracks"],
            id="duplicates-only",
        ),
        pytest.param(
            ["unavailable", "bloated"],
            ["unavailable or unplayable tracks", "oversized playlists"],
            id="combined-subset",
        ),
        pytest.param(["unknown"], [], id="unknown-area"),
    ],
)
def test_focus_hint_for_areas_describes_selected_subset(
    focus_areas: list[str],
    expected_fragments: list[str],
) -> None:
    """Verify focus hints are emitted only for selected subsets."""
    hint = _focus_hint_for_areas(focus_areas)

    if not expected_fragments:
        assert_that(hint).is_empty()
    for fragment in expected_fragments:
        assert_that(hint).contains(fragment)


@pytest.mark.parametrize(
    ("scan", "options", "expected_kinds"),
    [
        pytest.param(
            _scan(duplicate_tracks=5, unavailable_tracks=2, track_count=150),
            CleanupSuggestOptions(),
            ["duplicates", "unavailable", "split"],
            id="all-default-thresholds",
        ),
        pytest.param(
            _scan(duplicate_tracks=3, unavailable_tracks=2, track_count=120),
            CleanupSuggestOptions(
                min_duplicates=3,
                min_unavailable=2,
                min_bloated_tracks=120,
            ),
            ["duplicates", "unavailable", "split"],
            id="threshold-boundaries-are-inclusive",
        ),
        pytest.param(
            _scan(duplicate_tracks=3, unavailable_tracks=2, track_count=119),
            CleanupSuggestOptions(
                min_duplicates=4,
                min_unavailable=3,
                min_bloated_tracks=120,
            ),
            [],
            id="below-thresholds-are-suppressed",
        ),
        pytest.param(
            _scan(duplicate_tracks=0, unavailable_tracks=0, track_count=50),
            CleanupSuggestOptions(min_bloated_tracks=50),
            ["split"],
            id="zero-issue-counts-do-not-create-duplicate-or-unavailable-suggestions",
        ),
    ],
)
def test_heuristic_suggestions_respect_issue_thresholds(
    scan: dict[str, object],
    options: CleanupSuggestOptions,
    expected_kinds: list[str],
) -> None:
    """Verify fallback suggestions are built only when thresholds match."""
    result = _heuristic_suggestions([scan], options=options)
    suggestions = result["suggestions"]

    assert_that([suggestion["kind"] for suggestion in suggestions]).is_equal_to(
        expected_kinds,
    )
    if expected_kinds:
        assert_that(result["summary"]).contains(
            f"Found {len(expected_kinds)} cleanup opportunities",
        )
    else:
        assert_that(result["summary"]).is_equal_to(
            "No obvious cleanup issues found in scanned playlists.",
        )


@pytest.mark.parametrize(
    ("duplicate_tracks", "expected_priority"),
    [
        pytest.param(1, "medium", id="few-duplicates"),
        pytest.param(5, "high", id="many-duplicates"),
    ],
)
def test_heuristic_duplicate_suggestions_set_priority_by_count(
    duplicate_tracks: int,
    expected_priority: str,
) -> None:
    """Verify duplicate suggestion priority changes at five duplicates."""
    result = _heuristic_suggestions(
        [_scan(duplicate_tracks=duplicate_tracks)],
        options=CleanupSuggestOptions(min_bloated_tracks=50),
    )
    duplicates = [
        suggestion
        for suggestion in result["suggestions"]
        if suggestion["kind"] == "duplicates"
    ]

    assert_that(duplicates).is_length(1)
    assert_that(duplicates[0]["priority"]).is_equal_to(expected_priority)
