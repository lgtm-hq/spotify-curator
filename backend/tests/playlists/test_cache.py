"""Unit tests for cached playlist list helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from assertpy import assert_that
from sqlalchemy.orm import Session

from app.db import PlaylistListCacheRecord, PlaylistScanCacheRecord, dumps_json
from app.playlists.cache import (
    load_playlist_list_cache,
    patch_playlist_in_cache,
    playlist_cache_updated_at,
    playlists_from_scan_cache,
    save_playlist_list_cache,
)
from app.playlists.models import PlaylistSummary


def _playlist(
    playlist_id: str,
    *,
    name: str,
    library_order: int,
    owner: str = "You",
    owner_id: str = "user-1",
    can_edit: bool = True,
    track_count: int = 10,
) -> PlaylistSummary:
    """Build a playlist summary for cache tests."""
    return PlaylistSummary(
        id=playlist_id,
        name=name,
        owner=owner,
        owner_id=owner_id,
        track_count=track_count,
        can_edit=can_edit,
        library_order=library_order,
    )


def test_save_and_load_playlist_list_cache_round_trips_models(
    session: Session,
) -> None:
    """Verify cached playlist lists round-trip through persisted JSON."""
    playlists = [
        _playlist("playlist-1", name="Road Trip", library_order=0),
        _playlist(
            "playlist-2",
            name="Shared Mix",
            library_order=1,
            owner="Friend",
            owner_id="friend-1",
            can_edit=False,
            track_count=25,
        ),
    ]

    save_playlist_list_cache(session, playlists)
    loaded = load_playlist_list_cache(session)

    assert_that(loaded).is_not_none()
    assert_that([item.model_dump() for item in loaded or []]).is_equal_to(
        [item.model_dump() for item in playlists],
    )
    assert_that(playlist_cache_updated_at(session)).is_not_none()


def test_load_playlist_list_cache_backfills_legacy_library_order(
    session: Session,
) -> None:
    """Verify older cache rows without library_order load in list order."""
    session.add(
        PlaylistListCacheRecord(
            id=1,
            playlists_json=dumps_json(
                [
                    {
                        "id": "playlist-1",
                        "name": "First",
                        "owner": "You",
                        "track_count": 10,
                    },
                    {
                        "id": "playlist-2",
                        "name": "Second",
                        "owner": "You",
                        "track_count": 20,
                    },
                ],
            ),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    )
    session.commit()

    loaded = load_playlist_list_cache(session)

    assert_that([item.library_order for item in loaded or []]).is_equal_to([0, 1])


def test_patch_playlist_in_cache_preserves_library_order(
    session: Session,
) -> None:
    """Verify patching updates a row without moving it in the library."""
    save_playlist_list_cache(
        session,
        [
            _playlist("playlist-1", name="Keep", library_order=3),
            _playlist("playlist-2", name="Before", library_order=8),
        ],
    )
    updated = _playlist(
        "playlist-2",
        name="After",
        library_order=0,
        track_count=99,
    )

    patch_playlist_in_cache(session, updated)
    loaded = load_playlist_list_cache(session)

    assert_that(loaded).is_not_none()
    patched = [item for item in loaded or [] if item.id == "playlist-2"][0]
    assert_that(patched.name).is_equal_to("After")
    assert_that(patched.track_count).is_equal_to(99)
    assert_that(patched.library_order).is_equal_to(8)


def test_playlists_from_scan_cache_builds_sorted_fallback_list(
    session: Session,
) -> None:
    """Verify scan summaries can seed an offline playlist list."""
    now = datetime.now(UTC)
    session.add_all(
        [
            PlaylistScanCacheRecord(
                playlist_id="playlist-b",
                scan_json=dumps_json(
                    {
                        "playlist_id": "playlist-b",
                        "playlist_name": "Zebra",
                        "track_count": 12,
                        "tracks_scanned": 12,
                        "duplicate_tracks": 0,
                        "unavailable_tracks": 0,
                        "owned": False,
                        "full_scan": True,
                    },
                ),
                updated_at=now,
            ),
            PlaylistScanCacheRecord(
                playlist_id="playlist-a",
                scan_json=dumps_json(
                    {
                        "playlist_id": "playlist-a",
                        "playlist_name": "Alpha",
                        "track_count": 7,
                        "tracks_scanned": 7,
                        "duplicate_tracks": 1,
                        "unavailable_tracks": 0,
                        "owned": True,
                        "full_scan": True,
                    },
                ),
                updated_at=now,
            ),
        ],
    )
    session.commit()

    loaded = playlists_from_scan_cache(session)

    assert_that(loaded).is_not_none()
    assert_that([item.id for item in loaded or []]).is_equal_to(
        ["playlist-a", "playlist-b"],
    )
    assert_that([(item.owner, item.can_edit) for item in loaded or []]).is_equal_to(
        [("You", True), ("Unknown", False)],
    )
