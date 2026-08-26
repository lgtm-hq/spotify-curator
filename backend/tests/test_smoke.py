"""Smoke tests for the FastAPI application."""

from __future__ import annotations

import pytest
from assertpy import assert_that
from fastapi.testclient import TestClient

PROTECTED_ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("GET", "/playlists"),
    ("GET", "/cleanup/ai/presets"),
    ("POST", "/discover/generate"),
    ("POST", "/curate/start"),
    ("GET", "/taste"),
)


def test_openapi_schema_builds(client: TestClient) -> None:
    """Verify the app exposes a valid OpenAPI schema."""
    response = client.get("/openapi.json")

    assert_that(response.status_code).is_equal_to(200)
    schema = response.json()
    assert_that(schema["info"]["title"]).is_equal_to("Spotify Curator")
    assert_that(schema["paths"]).contains("/playlists")


@pytest.mark.parametrize(
    ("method", "path"),
    PROTECTED_ENDPOINTS,
    ids=[
        "prefix=playlists",
        "prefix=cleanup",
        "prefix=discover",
        "prefix=curate",
        "prefix=taste",
    ],
)
def test_protected_routes_require_session(
    client: TestClient,
    method: str,
    path: str,
) -> None:
    """Verify protected API routes reject anonymous requests."""
    response = client.request(method=method, url=path)

    assert_that(response.status_code).is_equal_to(401)
    assert_that(response.json()).is_equal_to({"detail": "Not authenticated"})


def test_authenticated_client_uses_dependency_overrides(
    authenticated_client: TestClient,
) -> None:
    """Verify fake auth and database overrides exercise an existing route."""
    response = authenticated_client.get("/playlists")

    assert_that(response.status_code).is_equal_to(200)
    body = response.json()
    assert_that(body["playlists"]).is_empty()
    assert_that(body["from_cache"]).is_true()
    assert_that(body["spotify_usage"]["state"]).is_equal_to("ok")
