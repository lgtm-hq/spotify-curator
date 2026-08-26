"""Cached playlist list for Spotify rate-limit fallback."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.cleanup.playlist_scan import load_all_cached_stats
from app.db import PlaylistListCacheRecord, dumps_json, ensure_utc, loads_json, utcnow
from app.playlists.models import PlaylistSummary


def save_playlist_list_cache(db: Session, playlists: list[PlaylistSummary]) -> None:
    """Persist the latest playlist list from Spotify."""
    record = db.get(PlaylistListCacheRecord, 1)
    if record is None:
        record = PlaylistListCacheRecord(id=1)
        db.add(record)
    record.playlists_json = dumps_json([item.model_dump() for item in playlists])
    record.updated_at = utcnow()
    db.commit()


def load_playlist_list_cache(db: Session) -> list[PlaylistSummary] | None:
    """Return the last saved playlist list, if any."""
    record = db.get(PlaylistListCacheRecord, 1)
    if record is None:
        return None
    data = loads_json(record.playlists_json)
    if not isinstance(data, list) or not data:
        return None
    return [
        PlaylistSummary.model_validate(
            {
                **item,
                "library_order": item.get("library_order", index),
            },
        )
        for index, item in enumerate(data)
    ]


def playlist_cache_updated_at(db: Session) -> datetime | None:
    """Return when the playlist list cache was last refreshed from Spotify."""
    record = db.get(PlaylistListCacheRecord, 1)
    if record is None:
        return None
    return ensure_utc(record.updated_at)


def normalize_playlists_for_user(
    playlists: list[PlaylistSummary],
    *,
    current_user_id: str | None,
    current_user_display_name: str | None = None,
) -> list[PlaylistSummary]:
    """Repair cached playlist rows missing edit flags or owner ids."""
    if not current_user_id:
        return playlists

    normalized: list[PlaylistSummary] = []
    for playlist in playlists:
        owned = playlist.owner_id == current_user_id
        if not owned and not playlist.owner_id and current_user_display_name:
            owned = (
                playlist.owner.strip().casefold()
                == current_user_display_name.strip().casefold()
            )

        updates: dict[str, object] = {}
        if owned and not playlist.can_edit:
            updates["can_edit"] = True
        if owned and not playlist.owner_id:
            updates["owner_id"] = current_user_id
        if updates:
            playlist = playlist.model_copy(update=updates)
        normalized.append(playlist)
    return normalized


def repair_playlist_list_cache(
    db: Session,
    *,
    current_user_id: str | None,
    current_user_display_name: str | None = None,
) -> list[PlaylistSummary] | None:
    """Normalize and persist playlist cache when edit flags are stale."""
    playlists = load_playlist_list_cache(db)
    if not playlists or not current_user_id:
        return playlists
    normalized = normalize_playlists_for_user(
        playlists,
        current_user_id=current_user_id,
        current_user_display_name=current_user_display_name,
    )
    if any(
        left.can_edit != right.can_edit or left.owner_id != right.owner_id
        for left, right in zip(playlists, normalized, strict=True)
    ):
        save_playlist_list_cache(db, normalized)
    return normalized


def playlists_from_scan_cache(db: Session) -> list[PlaylistSummary] | None:
    """Build a minimal playlist list from scan cache when Spotify is unavailable."""
    stats = load_all_cached_stats(db)
    if not stats:
        return None
    playlists: list[PlaylistSummary] = []
    for playlist_id, data in stats.items():
        playlists.append(
            PlaylistSummary(
                id=playlist_id,
                name=str(data.get("playlist_name") or "Unknown"),
                track_count=int(data.get("track_count") or 0),
                owner="You" if data.get("owned") else "Unknown",
                owner_id="",
                can_edit=bool(data.get("owned")),
            ),
        )
    playlists.sort(key=lambda item: item.name.lower())
    return playlists or None


def patch_playlist_in_cache(db: Session, updated: PlaylistSummary) -> None:
    """Update one playlist row in the cached list."""
    playlists = load_playlist_list_cache(db)
    if not playlists:
        return
    for index, playlist in enumerate(playlists):
        if playlist.id == updated.id:
            playlists[index] = updated.model_copy(update={"library_order": playlist.library_order})
            save_playlist_list_cache(db, playlists)
            return


def remove_playlist_from_spotify_cache(db: Session, *, playlist_id: str) -> None:
    """Remove playlist rows from list and scan caches only."""
    from app.db import PlaylistScanCacheRecord

    playlists = load_playlist_list_cache(db)
    if playlists:
        filtered = [item for item in playlists if item.id != playlist_id]
        if len(filtered) != len(playlists):
            record = db.get(PlaylistListCacheRecord, 1)
            if record is not None:
                record.playlists_json = dumps_json([item.model_dump() for item in filtered])
                record.updated_at = utcnow()

    scan = db.get(PlaylistScanCacheRecord, playlist_id)
    if scan is not None:
        db.delete(scan)


def purge_playlist_local_references(db: Session, *, playlist_id: str) -> None:
    """Drop cached playlist data and app references after unfollow."""
    from app.db import CurateSessionRecord, DiscoverRunRecord

    remove_playlist_from_spotify_cache(db, playlist_id=playlist_id)

    db.query(DiscoverRunRecord).filter(
        DiscoverRunRecord.playlist_id == playlist_id,
    ).delete(synchronize_session=False)
    db.query(CurateSessionRecord).filter(
        CurateSessionRecord.spotify_playlist_id == playlist_id,
    ).update(
        {CurateSessionRecord.spotify_playlist_id: None},
        synchronize_session=False,
    )
    db.commit()
