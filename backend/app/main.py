"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hooks."""
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    """Create and configure FastAPI app."""
    settings = get_settings()
    app = FastAPI(title="Spotify Curator", lifespan=lifespan)
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
    return app


app = create_app()
