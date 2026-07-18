"""Spotify OAuth 2.0 helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import urlencode

import httpx
import jwt
from jwt.exceptions import InvalidTokenError

from app.config import get_settings

AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_ENDPOINT = (  # nosec B105 - public OAuth endpoint URL, not a credential
    "https://accounts.spotify.com/api/token"
)
STATE_ALGORITHM = "HS256"
STATE_MINUTES = 10


def generate_state() -> str:
    """Generate a signed CSRF state token."""
    settings = get_settings()
    payload = {
        "purpose": "spotify_oauth",
        "exp": datetime.now(UTC) + timedelta(minutes=STATE_MINUTES),
    }
    return cast(
        str,
        jwt.encode(payload, settings.secret_key, algorithm=STATE_ALGORITHM),
    )


def validate_state(state: str) -> bool:
    """Validate a signed CSRF state token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            state,
            settings.secret_key,
            algorithms=[STATE_ALGORITHM],
        )
    except InvalidTokenError:
        return False
    return bool(payload.get("purpose") == "spotify_oauth")


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
            SPOTIFY_TOKEN_ENDPOINT,
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
        return cast(dict[str, object], response.json())


async def refresh_access_token(*, refresh_token: str) -> dict[str, object]:
    """Refresh an expired access token."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SPOTIFY_TOKEN_ENDPOINT,
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
        return cast(dict[str, object], response.json())
