"""Smoke tests for the FastAPI app factory."""

from app.main import create_app


def test_create_app_returns_spotify_curator_app() -> None:
    """Create the app without starting lifespan side effects."""
    app = create_app()

    assert app.title == "Spotify Curator"
