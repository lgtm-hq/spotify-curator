"""Unit tests for cleanup advisor presets."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from assertpy import assert_that
from sqlalchemy.orm import Session

from app.cleanup import advisor_presets
from app.cleanup.advisor_presets import (
    BUILTIN_QUICK_STARTS,
    delete_preset,
    list_presets,
    quick_start_context,
    save_preset,
)
from app.cleanup.suggest_options import CleanupSuggestOptions

FROZEN_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("quick_start_id", "expected_fragment"),
    [
        pytest.param(None, "", id="none"),
        pytest.param("does-not-exist", "", id="unknown"),
        pytest.param("quick-dupes", "duplicate tracks", id="known"),
    ],
)
def test_quick_start_context_returns_builtin_guidance(
    quick_start_id: str | None,
    expected_fragment: str,
) -> None:
    """Verify quick-start ids map to built-in AI guidance text."""
    context = quick_start_context(quick_start_id)

    assert_that(context).contains(expected_fragment)


def test_list_presets_returns_builtins_before_saved_configuration(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify preset listing merges built-ins with saved configurations."""
    monkeypatch.setattr(advisor_presets, "utcnow", lambda: FROZEN_NOW)
    saved = save_preset(
        session,
        name="  Dedupe weekly  ",
        description="  Tight duplicate threshold  ",
        options=CleanupSuggestOptions(
            scope="selected",
            playlist_ids=["playlist-1"],
            focus_areas=["duplicates"],
            min_duplicates=3,
            quick_start_id="quick-dupes",
        ),
    )

    presets = list_presets(session)

    assert_that(
        [preset["id"] for preset in presets[: len(BUILTIN_QUICK_STARTS)]]
    ).is_equal_to(
        [preset["id"] for preset in BUILTIN_QUICK_STARTS],
    )
    assert_that(presets[-1]).is_equal_to(saved)
    assert_that(presets[-1]["name"]).is_equal_to("Dedupe weekly")
    assert_that(presets[-1]["description"]).is_equal_to("Tight duplicate threshold")
    assert_that(presets[-1]["options"]).does_not_contain_key("quick_start_id")
    assert_that(presets[-1]["options"]).contains_entry({"scope": "selected"})
    assert_that(presets[-1]["options"]).contains_entry(
        {"playlist_ids": ["playlist-1"]},
    )
    assert_that(presets[-1]["options"]).contains_entry(
        {"focus_areas": ["duplicates"]},
    )
    assert_that(presets[-1]["options"]).contains_entry({"min_duplicates": 3})


def test_delete_preset_refuses_builtins_and_removes_saved_preset(
    session: Session,
) -> None:
    """Verify only user-saved advisor presets can be deleted."""
    saved = save_preset(
        session,
        name="Delete me",
        options=CleanupSuggestOptions(focus_areas=["unavailable"]),
    )

    deleted_builtin = delete_preset(session, "full-audit")
    deleted_saved = delete_preset(session, str(saved["id"]))
    deleted_again = delete_preset(session, str(saved["id"]))

    assert_that(deleted_builtin).is_false()
    assert_that(deleted_saved).is_true()
    assert_that(deleted_again).is_false()
    assert_that([preset["id"] for preset in list_presets(session)]).does_not_contain(
        saved["id"],
    )
