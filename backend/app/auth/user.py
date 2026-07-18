"""Persist Spotify user profile for the connected account."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db import UserRecord, utcnow
from app.spotify_client import create_spotify_client


def save_user_profile(db: Session, *, profile: dict[str, Any]) -> UserRecord:
    """Store Spotify profile fields for the connected account."""
    images = profile.get("images") or []
    record = db.get(UserRecord, 1)
    if record is None:
        record = UserRecord(id=1, connected_at=utcnow())
        db.add(record)

    record.spotify_id = str(profile.get("id", ""))
    record.display_name = str(
        profile.get("display_name") or profile.get("id") or "Spotify user"
    )
    record.email = profile.get("email")
    record.image_url = images[0]["url"] if images else None
    record.product = profile.get("product")
    record.connected_at = record.connected_at or utcnow()
    db.commit()
    return record


def fetch_and_save_user_profile(db: Session, *, access_token: str) -> UserRecord:
    """Load the current Spotify user and persist it."""
    sp = create_spotify_client(access_token)
    return save_user_profile(db, profile=sp.me())


def user_to_dict(record: UserRecord | None) -> dict[str, Any] | None:
    """Serialize a user record for API responses."""
    if record is None:
        return None
    return {
        "spotify_id": record.spotify_id,
        "display_name": record.display_name,
        "email": record.email,
        "image_url": record.image_url,
        "product": record.product,
        "connected_at": record.connected_at.isoformat(),
    }
