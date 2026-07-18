"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from spotipy.exceptions import SpotifyException
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from app.ai.router import router as ai_router
from app.auth.router import router as auth_router
from app.cleanup.router import router as cleanup_router
from app.config import get_settings
from app.curate.router import router as curate_router
from app.db import init_db
from app.discover.router import router as discover_router
from app.playlists.router import router as playlists_router
from app.scheduler import start_scheduler, stop_scheduler
from app.taste.router import router as taste_router

logger = logging.getLogger(__name__)
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class SPAStaticFiles(StaticFiles):
    """Serve Vite assets and fall back to index.html for SPA routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Return a static asset response or the SPA shell for client routes."""
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or not self._should_fallback_to_index(
                path, scope
            ):
                raise
            return await super().get_response("index.html", scope)

    def _should_fallback_to_index(self, path: str, scope: Scope) -> bool:
        """Return whether a 404 should fall back to the SPA shell."""
        method = scope.get("method")
        if method not in {"GET", "HEAD"}:
            return False
        headers = dict(scope.get("headers") or [])
        accept = headers.get(b"accept", b"").decode("latin-1")
        return "text/html" in accept


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hooks."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    """Create and configure FastAPI app."""
    settings = get_settings()
    app = FastAPI(title="Spotify Curator", lifespan=lifespan)

    @app.exception_handler(SpotifyException)
    async def spotify_exception_handler(
        request: Request,
        exc: SpotifyException,
    ) -> JSONResponse:
        logger.error("Spotify API error on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=502,
            content={"detail": f"Spotify API error: {exc}"},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_url,
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(ai_router)
    app.include_router(playlists_router)
    app.include_router(cleanup_router)
    app.include_router(curate_router)
    app.include_router(discover_router)
    app.include_router(taste_router)
    if FRONTEND_DIST.is_dir():
        app.mount(
            "/",
            SPAStaticFiles(directory=FRONTEND_DIST, html=True),
            name="frontend",
        )
    return app


app = create_app()
