"""Unit tests for Spotify API usage accounting."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from assertpy import assert_that
from sqlalchemy.orm import Session

from app import spotify_usage
from app.db import SpotifyUsageRecord
from app.spotify_usage import (
    ESTIMATED_LIMIT,
    WARNING_THRESHOLD,
    WINDOW_SECONDS,
    record_rate_limit,
    record_spotify_request,
    retry_after_from_exception,
    usage_status,
)


def _freeze_time(monkeypatch: pytest.MonkeyPatch, frozen: datetime) -> None:
    """Make spotify usage helpers read a deterministic clock."""
    monkeypatch.setattr(spotify_usage, "utcnow", lambda: frozen)


def _store_usage_record(
    session: Session,
    *,
    timestamps: list[datetime],
    rate_limited_until: datetime | None = None,
) -> SpotifyUsageRecord:
    """Persist a synthetic usage record."""
    record = SpotifyUsageRecord(
        id=1,
        request_timestamps_json=json.dumps(
            [timestamp.isoformat() for timestamp in timestamps],
        ),
        rate_limited_until=rate_limited_until,
    )
    session.add(record)
    session.commit()
    return record


def test_record_spotify_request_prunes_expired_entries(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify recording requests keeps only the active rolling window."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    _freeze_time(monkeypatch, now)
    record = _store_usage_record(
        session,
        timestamps=[
            now - timedelta(seconds=WINDOW_SECONDS + 1),
            now - timedelta(seconds=WINDOW_SECONDS),
            now - timedelta(seconds=5),
        ],
    )

    record_spotify_request(session, count=3)

    session.refresh(record)
    stored = json.loads(record.request_timestamps_json)
    assert_that(stored).is_length(5)
    assert_that(stored).does_not_contain(
        (now - timedelta(seconds=WINDOW_SECONDS + 1)).isoformat(),
    )
    assert_that(stored).contains(
        (now - timedelta(seconds=WINDOW_SECONDS)).isoformat(),
    )
    assert_that(stored.count(now.isoformat())).is_equal_to(3)


@pytest.mark.parametrize(
    ("request_count", "expected_state", "expected_percent"),
    [
        pytest.param(
            int(ESTIMATED_LIMIT * WARNING_THRESHOLD) - 1,
            "ok",
            69,
            id="just-below-warning",
        ),
        pytest.param(
            int(ESTIMATED_LIMIT * WARNING_THRESHOLD),
            "warning",
            70,
            id="at-warning-threshold",
        ),
        pytest.param(
            ESTIMATED_LIMIT + 5,
            "warning",
            100,
            id="above-estimated-limit-clamps-percent",
        ),
    ],
)
def test_usage_status_reports_threshold_edges(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    request_count: int,
    expected_state: str,
    expected_percent: int,
) -> None:
    """Verify usage state changes at warning and limit boundaries."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    _freeze_time(monkeypatch, now)
    _store_usage_record(
        session,
        timestamps=[now - timedelta(seconds=1) for _ in range(request_count)],
    )

    status = usage_status(
        session,
        last_fetched_at=now - timedelta(seconds=10),
    )

    assert_that(status).contains_entry({"state": expected_state})
    assert_that(status).contains_entry({"requests_in_window": request_count})
    assert_that(status).contains_entry({"usage_percent": expected_percent})
    assert_that(status).contains_entry(
        {"last_fetched_at": (now - timedelta(seconds=10)).isoformat()},
    )


@pytest.mark.parametrize(
    ("retry_after_seconds", "expected_seconds"),
    [
        pytest.param(None, 60, id="missing-retry-after-defaults"),
        pytest.param(0, 60, id="zero-retry-after-defaults"),
        pytest.param(-5, 60, id="negative-retry-after-defaults"),
        pytest.param(12, 12, id="positive-retry-after-is-used"),
    ],
)
def test_record_rate_limit_sets_limited_state(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    retry_after_seconds: int | None,
    expected_seconds: int,
) -> None:
    """Verify Retry-After values are persisted for UI backoff."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    _freeze_time(monkeypatch, now)

    record_rate_limit(session, retry_after_seconds=retry_after_seconds)
    status = usage_status(session)

    assert_that(status).contains_entry({"state": "limited"})
    assert_that(status).contains_entry({"seconds_until_reset": expected_seconds})
    assert_that(status["rate_limited_until"]).is_equal_to(
        (now + timedelta(seconds=expected_seconds)).isoformat(),
    )


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        pytest.param({"Retry-After": "9"}, 9, id="integer-header"),
        pytest.param({"Retry-After": "not-a-number"}, None, id="invalid-header"),
        pytest.param({}, None, id="missing-header"),
    ],
)
def test_retry_after_from_exception_parses_header(
    headers: dict[str, Any],
    expected: int | None,
) -> None:
    """Verify Spotipy Retry-After parsing is tolerant of malformed headers."""
    assert_that(
        retry_after_from_exception(SimpleNamespace(headers=headers)),
    ).is_equal_to(expected)
