"""Tests for Spotify OAuth user persistence."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from assertpy import assert_that
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.user import save_user_profile, user_to_dict
from app.db import Base, User


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Yield an isolated in-memory database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_save_user_profile_upserts_by_spotify_id(db_session: Session) -> None:
    """Verify repeated OAuth callbacks update the same user row."""
    created = save_user_profile(
        db_session,
        profile={
            "id": "spotify-1",
            "display_name": "First Name",
            "email": "first@example.com",
            "images": [{"url": "https://example.com/first.jpg"}],
            "product": "premium",
        },
    )

    updated = save_user_profile(
        db_session,
        profile={
            "id": "spotify-1",
            "display_name": "Updated Name",
            "email": "updated@example.com",
            "images": [{"url": "https://example.com/updated.jpg"}],
            "product": "free",
        },
    )

    users = db_session.scalars(select(User)).all()
    assert_that(users).is_length(1)
    assert_that(updated.id).is_equal_to(created.id)
    assert_that(updated.spotify_id).is_equal_to("spotify-1")
    assert_that(updated.display_name).is_equal_to("Updated Name")
    assert_that(updated.email).is_equal_to("updated@example.com")
    assert_that(updated.image_url).is_equal_to("https://example.com/updated.jpg")
    assert_that(updated.product).is_equal_to("free")


def test_save_user_profile_marks_only_first_user_admin(db_session: Session) -> None:
    """Verify the first persisted Spotify identity becomes admin."""
    first = save_user_profile(
        db_session,
        profile={"id": "spotify-1", "display_name": "First"},
    )
    second = save_user_profile(
        db_session,
        profile={"id": "spotify-2", "display_name": "Second"},
    )

    assert_that(first.is_admin).is_true()
    assert_that(second.is_admin).is_false()


def test_user_to_dict_serializes_identity_fields(db_session: Session) -> None:
    """Verify API serialization includes identity and admin metadata."""
    user = save_user_profile(
        db_session,
        profile={
            "id": "spotify-1",
            "display_name": "First",
            "email": "first@example.com",
            "images": [{"url": "https://example.com/first.jpg"}],
            "product": "premium",
        },
    )

    payload = user_to_dict(user)

    assert_that(payload).contains_entry({"id": user.id})
    assert_that(payload).contains_entry({"spotify_id": "spotify-1"})
    assert_that(payload).contains_entry({"display_name": "First"})
    assert_that(payload).contains_entry({"email": "first@example.com"})
    assert_that(payload).contains_entry({"image_url": "https://example.com/first.jpg"})
    assert_that(payload).contains_entry({"product": "premium"})
    assert_that(payload).contains_entry({"is_admin": True})
    assert_that(payload).contains_key("created_at")
    assert_that(payload).contains_key("connected_at")
