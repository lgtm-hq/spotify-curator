"""Shared API error helpers."""

from __future__ import annotations

import logging

from fastapi import HTTPException
from spotipy.exceptions import SpotifyException

from app.ai.exceptions import (
    AIAuthenticationError,
    AINotAvailableError,
    AIProviderError,
)

logger = logging.getLogger(__name__)


def raise_curate_http_error(exc: Exception, *, action: str) -> None:
    """Log and translate curate failures into HTTP errors."""
    if isinstance(exc, HTTPException):
        raise exc

    logger.exception("Curate %s failed", action)

    if isinstance(exc, ValueError):
        status = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    if isinstance(exc, (AIAuthenticationError, AINotAvailableError)):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, AIProviderError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, SpotifyException):
        raise HTTPException(
            status_code=502,
            detail=f"Spotify API error: {exc}",
        ) from exc
    raise HTTPException(status_code=500, detail="An unexpected error occurred") from exc
