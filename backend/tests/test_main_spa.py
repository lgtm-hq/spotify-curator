"""Tests for serving the packaged SPA from FastAPI."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main


def _write_dist(dist_dir: Path) -> None:
    """Create a minimal Vite dist directory for StaticFiles tests."""
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text(
        "<!doctype html><title>Spotify Curator SPA</title>",
        encoding="utf-8",
    )
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir()
    (assets_dir / "app.js").write_text(
        "console.log('spotify-curator');",
        encoding="utf-8",
    )


def test_spa_mount_serves_static_assets_and_client_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Serve static assets and fall back to index.html for SPA routes."""
    dist_dir = tmp_path / "dist"
    _write_dist(dist_dir)
    monkeypatch.setattr(main, "FRONTEND_DIST", dist_dir)

    client = TestClient(main.create_app())

    asset_response = client.get("/assets/app.js")
    assert asset_response.status_code == 200
    assert "spotify-curator" in asset_response.text

    route_response = client.get("/cleanup", headers={"accept": "text/html"})
    assert route_response.status_code == 200
    assert "Spotify Curator SPA" in route_response.text


def test_api_and_docs_routes_take_precedence_over_spa(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep existing API and documentation routes ahead of the SPA mount."""
    dist_dir = tmp_path / "dist"
    _write_dist(dist_dir)
    monkeypatch.setattr(main, "FRONTEND_DIST", dist_dir)

    client = TestClient(main.create_app())

    docs_response = client.get("/docs")
    assert docs_response.status_code == 200
    assert "swagger-ui" in docs_response.text

    auth_response = client.get("/auth/login", follow_redirects=False)
    assert auth_response.status_code in {307, 302}
