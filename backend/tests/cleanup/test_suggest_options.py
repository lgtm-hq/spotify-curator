"""Unit tests for cleanup advisor scan options."""

from __future__ import annotations

import pytest
from assertpy import assert_that

from app.cleanup.suggest_options import ALL_FOCUS_AREAS, CleanupSuggestOptions


def test_default_focus_areas_cover_every_advisor_area() -> None:
    """Verify default scan options include all advisor focus areas."""
    options = CleanupSuggestOptions()

    assert_that(options.focus_areas).is_equal_to(ALL_FOCUS_AREAS)
    assert_that(options.resolved_focus_areas()).is_equal_to(ALL_FOCUS_AREAS)


def test_empty_focus_areas_resolve_to_all_areas() -> None:
    """Verify an empty focus selection means a full advisor scan."""
    options = CleanupSuggestOptions(focus_areas=[])

    assert_that(options.resolved_focus_areas()).is_equal_to(ALL_FOCUS_AREAS)


@pytest.mark.parametrize(
    ("payload", "expected_focus_areas"),
    [
        pytest.param({"focus": None}, ALL_FOCUS_AREAS, id="none-means-all"),
        pytest.param({"focus": "all"}, ALL_FOCUS_AREAS, id="all-means-all"),
        pytest.param({"focus": "duplicates"}, ["duplicates"], id="single-focus"),
        pytest.param(
            {"focus": "duplicates", "focus_areas": ["unavailable"]},
            ["unavailable"],
            id="explicit-focus-areas-win",
        ),
    ],
)
def test_legacy_focus_field_maps_to_focus_areas(
    payload: dict[str, object],
    expected_focus_areas: list[str],
) -> None:
    """Verify deprecated single-focus payloads normalize to focus areas."""
    options = CleanupSuggestOptions.model_validate(dict(payload))

    assert_that(options.focus_areas).is_equal_to(expected_focus_areas)
    assert_that(options.resolved_focus_areas()).is_equal_to(expected_focus_areas)


@pytest.mark.parametrize(
    ("use_scan_cache", "force_rescan", "expected"),
    [
        pytest.param(True, False, True, id="default-cache-enabled"),
        pytest.param(True, True, False, id="force-rescan-disables-cache"),
        pytest.param(False, False, False, id="cache-disabled"),
        pytest.param(False, True, False, id="cache-disabled-and-force-rescan"),
    ],
)
def test_effective_use_cache_combines_cache_flags(
    use_scan_cache: bool,
    force_rescan: bool,
    expected: bool,
) -> None:
    """Verify cache usage honors both cache and force-rescan flags."""
    options = CleanupSuggestOptions(
        use_scan_cache=use_scan_cache,
        force_rescan=force_rescan,
    )

    assert_that(options.effective_use_cache()).is_equal_to(expected)
