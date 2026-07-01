"""Spotify OAuth 2.0 helpers."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app.config import get_settings

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

_oauth_states: dict[str, datetime] = {}


def generate_state() -> str:
    """Generate and store a CSRF state token."""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = datetime.now(timezone.utc)
    return state


def validate_state(state: str) -> bool:
    """Validate and consume a CSRF state token."""
    created = _oauth_states.pop(state, None)
    if created is None:
        return False
    return datetime.now(timezone.utc) - created < timedelta(minutes=10)


def build_auth_url(*, state: str) -> str:
    """Build Spotify authorization URL."""
    settings = get_settings()
    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": settings.spotify_scopes,
        "state": state,
        "show_dialog": "false",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(*, code: str) -> dict[str, object]:
    """Exchange authorization code for tokens."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.spotify_redirect_uri,
                "client_id": settings.spotify_client_id,
                "client_secret": settings.spotify_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(*, refresh_token: str) -> dict[str, object]:
    """Refresh an expired access token."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.spotify_client_id,
                "client_secret": settings.spotify_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
