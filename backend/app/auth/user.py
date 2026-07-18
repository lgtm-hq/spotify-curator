"""Persist Spotify user profiles keyed by Spotify identity."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import User, utcnow
from app.spotify_client import create_spotify_client


def get_user_by_spotify_id(db: Session, *, spotify_id: str) -> User | None:
    """Return the user matching a Spotify account id."""
    record: User | None = db.scalars(
        select(User).where(User.spotify_id == spotify_id),
    ).one_or_none()
    return record


def save_user_profile(db: Session, *, profile: dict[str, Any]) -> User:
    """Upsert Spotify profile fields by Spotify account id."""
    spotify_id = str(profile.get("id") or "")
    if not spotify_id:
        raise ValueError("Spotify profile did not include an id")

    images = profile.get("images") or []
    record = get_user_by_spotify_id(db, spotify_id=spotify_id)
    if record is None:
        is_first_user = db.scalar(select(User.id).limit(1)) is None
        now = utcnow()
        record = User(
            spotify_id=spotify_id,
            connected_at=now,
            created_at=now,
            is_admin=is_first_user,
        )
        db.add(record)

    record.display_name = str(
        profile.get("display_name") or spotify_id or "Spotify user",
    )
    record.email = profile.get("email")
    record.image_url = images[0]["url"] if images else None
    record.product = profile.get("product")
    record.connected_at = utcnow()
    db.commit()
    db.refresh(record)
    return record


def fetch_and_save_user_profile(db: Session, *, access_token: str) -> User:
    """Load the current Spotify user and persist it."""
    sp = create_spotify_client(access_token)
    return save_user_profile(db, profile=sp.me())


def user_to_dict(record: User | None) -> dict[str, Any] | None:
    """Serialize a user record for API responses."""
    if record is None:
        return None
    return {
        "id": record.id,
        "spotify_id": record.spotify_id,
        "display_name": record.display_name,
        "email": record.email,
        "image_url": record.image_url,
        "product": record.product,
        "is_admin": record.is_admin,
        "created_at": record.created_at.isoformat(),
        "connected_at": record.connected_at.isoformat(),
    }
