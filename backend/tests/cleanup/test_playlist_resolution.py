"""Unit tests for cleanup advisor playlist resolution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import pytest
from assertpy import assert_that

from app.cleanup import playlist_resolution
from app.cleanup.playlist_resolution import estimate_scan, resolve_playlists_to_scan
from app.cleanup.suggest_options import CleanupSuggestOptions
from app.playlists.models import PlaylistSummary

FROZEN_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
SortBy = Literal[
    "track_count_desc",
    "track_count_asc",
    "name_asc",
    "name_desc",
    "stale_first",
    "recently_scanned",
]


def _playlist(
    playlist_id: str,
    name: str,
    *,
    track_count: int = 25,
    can_edit: bool = True,
) -> PlaylistSummary:
    """Build a playlist summary for resolver tests."""
    return PlaylistSummary(
        id=playlist_id,
        name=name,
        owner="Test User",
        owner_id="test-user",
        track_count=track_count,
        can_edit=can_edit,
    )


def _ids(playlists: list[PlaylistSummary]) -> list[str]:
    """Return playlist ids in order."""
    return [playlist.id for playlist in playlists]


@pytest.mark.parametrize(
    ("cache_ages", "expected"),
    [
        pytest.param({}, True, id="missing-cache-is-stale"),
        pytest.param(
            {"playlist": FROZEN_NOW - timedelta(days=7)},
            False,
            id="exact-threshold-is-fresh",
        ),
        pytest.param(
            {"playlist": FROZEN_NOW - timedelta(days=7, seconds=1)},
            True,
            id="older-than-threshold-is-stale",
        ),
        pytest.param(
            {"playlist": FROZEN_NOW - timedelta(days=1)},
            False,
            id="newer-cache-is-fresh",
        ),
    ],
)
def test_is_stale_uses_strict_day_boundary(
    monkeypatch: pytest.MonkeyPatch,
    cache_ages: dict[str, datetime],
    expected: bool,
) -> None:
    """Verify stale checks treat the configured day threshold as exclusive."""
    monkeypatch.setattr(playlist_resolution, "utcnow", lambda: FROZEN_NOW)

    is_stale = playlist_resolution._is_stale(
        "playlist",
        stale_after_days=7,
        cache_ages=cache_ages,
    )

    assert_that(is_stale).is_equal_to(expected)


@pytest.mark.parametrize(
    ("options", "expected_ids"),
    [
        pytest.param(
            CleanupSuggestOptions(scope="all_owned", sort_by="track_count_desc"),
            ["large", "small"],
            id="owned-scope-sorts-largest-first",
        ),
        pytest.param(
            CleanupSuggestOptions(
                scope="selected",
                playlist_ids=["guest", "small"],
                sort_by="name_desc",
            ),
            ["guest", "small"],
            id="selected-scope-keeps-selected-playlists",
        ),
        pytest.param(
            CleanupSuggestOptions(
                scope="all_in_library",
                exclude_playlist_ids=["guest"],
                min_track_count=10,
                sort_by="track_count_asc",
            ),
            ["small", "large"],
            id="library-scope-applies-excludes-and-minimum-size",
        ),
    ],
)
def test_resolve_playlists_applies_scope_filters_and_sorting(
    monkeypatch: pytest.MonkeyPatch,
    options: CleanupSuggestOptions,
    expected_ids: list[str],
) -> None:
    """Verify resolver filters cached playlists without Spotify calls."""
    monkeypatch.setattr(playlist_resolution, "_scan_cache_ages", lambda db: {})
    playlists = [
        _playlist("small", "Alpha", track_count=25),
        _playlist("guest", "Zulu", track_count=80, can_edit=False),
        _playlist("large", "Charlie", track_count=200),
        _playlist("empty", "Empty", track_count=0),
    ]

    to_scan, library = resolve_playlists_to_scan(
        object(),
        current_user_id="test-user",
        options=options,
        cached_playlists=playlists,
    )

    assert_that(_ids(to_scan)).is_equal_to(expected_ids)
    assert_that(library).is_equal_to(playlists)


@pytest.mark.parametrize(
    ("sort_by", "expected_ids"),
    [
        pytest.param("stale_first", ["missing", "old", "fresh"], id="stale-first"),
        pytest.param(
            "recently_scanned",
            ["fresh", "old", "missing"],
            id="recently-scanned",
        ),
    ],
)
def test_resolve_playlists_sorts_by_cache_age(
    monkeypatch: pytest.MonkeyPatch,
    sort_by: SortBy,
    expected_ids: list[str],
) -> None:
    """Verify cache-age sort modes order missing and scanned playlists."""
    cache_ages = {
        "old": FROZEN_NOW - timedelta(days=30),
        "fresh": FROZEN_NOW - timedelta(hours=1),
    }
    monkeypatch.setattr(playlist_resolution, "_scan_cache_ages", lambda db: cache_ages)
    playlists = [
        _playlist("fresh", "Fresh"),
        _playlist("missing", "Missing"),
        _playlist("old", "Old"),
    ]

    to_scan, _library = resolve_playlists_to_scan(
        object(),
        current_user_id="test-user",
        options=CleanupSuggestOptions(scope="all_in_library", sort_by=sort_by),
        cached_playlists=playlists,
    )

    assert_that(_ids(to_scan)).is_equal_to(expected_ids)


def test_resolve_playlists_filters_fresh_scan_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify stale filtering keeps missing and old cache entries only."""
    monkeypatch.setattr(playlist_resolution, "utcnow", lambda: FROZEN_NOW)
    monkeypatch.setattr(
        playlist_resolution,
        "_scan_cache_ages",
        lambda db: {
            "fresh": FROZEN_NOW - timedelta(days=7),
            "old": FROZEN_NOW - timedelta(days=7, seconds=1),
        },
    )
    playlists = [
        _playlist("fresh", "Fresh"),
        _playlist("missing", "Missing"),
        _playlist("old", "Old"),
    ]

    to_scan, _library = resolve_playlists_to_scan(
        object(),
        current_user_id="test-user",
        options=CleanupSuggestOptions(
            scope="all_in_library",
            stale_after_days=7,
            sort_by="name_asc",
        ),
        cached_playlists=playlists,
    )

    assert_that(_ids(to_scan)).is_equal_to(["missing", "old"])


@pytest.mark.parametrize(
    ("options_kwargs", "cache_ages", "expected"),
    [
        pytest.param(
            {},
            {"cached": FROZEN_NOW - timedelta(minutes=30)},
            {
                "playlist_count": 4,
                "cached_count": 1,
                "fresh_scan_count": 1,
                "estimated_api_calls": 3,
                "estimated_seconds_min": 10,
                "estimated_seconds_max": 21,
            },
            id="fresh-cache-skips-api-estimate",
        ),
        pytest.param(
            {"force_rescan": True},
            {"cached": FROZEN_NOW - timedelta(minutes=30)},
            {
                "playlist_count": 4,
                "cached_count": 0,
                "fresh_scan_count": 2,
                "estimated_api_calls": 4,
                "estimated_seconds_min": 10,
                "estimated_seconds_max": 21,
            },
            id="force-rescan-ignores-cache",
        ),
        pytest.param(
            {"conservative_scan": True},
            {},
            {
                "playlist_count": 4,
                "cached_count": 0,
                "fresh_scan_count": 2,
                "estimated_api_calls": 4,
                "estimated_seconds_min": 10,
                "estimated_seconds_max": 21,
            },
            id="conservative-scan-estimates-with-two-workers",
        ),
    ],
)
def test_estimate_scan_counts_cache_and_fresh_work(
    monkeypatch: pytest.MonkeyPatch,
    options_kwargs: dict[str, Any],
    cache_ages: dict[str, datetime],
    expected: dict[str, int | float],
) -> None:
    """Verify scan estimates account for cache, editability, and track pages."""
    monkeypatch.setattr(playlist_resolution, "utcnow", lambda: FROZEN_NOW)
    monkeypatch.setattr(playlist_resolution, "_scan_cache_ages", lambda db: cache_ages)
    playlists = [
        _playlist("cached", "Cached", track_count=60),
        _playlist("fresh", "Fresh", track_count=250),
        _playlist("guest", "Guest", track_count=80, can_edit=False),
        _playlist("empty", "Empty", track_count=0),
    ]

    estimate = estimate_scan(
        playlists,
        options=CleanupSuggestOptions(**options_kwargs),
    )

    assert_that(estimate).is_equal_to(expected)
