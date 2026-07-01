"""Curate API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.router import get_current_user, get_db
from app.curate.prompt_engine import (
    answer_session,
    build_playlist_from_brief,
    save_playlist_to_spotify,
    start_session,
)
from app.errors import raise_curate_http_error
from app.spotify_client import get_spotify_client
from app.taste.engine import build_taste_profile, load_cached_taste_profile

router = APIRouter(prefix="/curate", tags=["curate"])


class AnswerRequest(BaseModel):
    """User answer to mood interview."""

    session_id: str
    answer: str


class BuildRequest(BaseModel):
    """Build or refine playlist."""

    session_id: str
    feedback: str | None = None


class SaveRequest(BaseModel):
    """Save playlist to Spotify."""

    session_id: str


@router.post("/start")
async def curate_start(
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Start mood concierge interview."""
    try:
        taste = load_cached_taste_profile(db)
        if taste is None:
            sp = await get_spotify_client(db)
            taste = build_taste_profile(sp, db=db)
        return start_session(db=db, taste_profile=taste)
    except Exception as exc:
        raise_curate_http_error(exc, action="start")


@router.post("/answer")
async def curate_answer(
    body: AnswerRequest,
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Answer interview question."""
    try:
        taste = load_cached_taste_profile(db)
        if taste is None:
            sp = await get_spotify_client(db)
            taste = build_taste_profile(sp, db=db)
        return answer_session(
            db=db,
            session_id=body.session_id,
            answer=body.answer,
            taste_profile=taste,
        )
    except Exception as exc:
        raise_curate_http_error(exc, action="answer")


@router.post("/build")
async def curate_build(
    body: BuildRequest,
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Build playlist from interview brief."""
    try:
        sp = await get_spotify_client(db)
        taste = load_cached_taste_profile(db) or build_taste_profile(sp, db=db)
        return build_playlist_from_brief(
            sp=sp,
            db=db,
            session_id=body.session_id,
            taste_profile=taste,
            feedback=body.feedback,
        )
    except Exception as exc:
        raise_curate_http_error(exc, action="build")


@router.post("/save")
async def curate_save(
    body: SaveRequest,
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Save curated playlist to Spotify."""
    try:
        sp = await get_spotify_client(db)
        return save_playlist_to_spotify(sp=sp, db=db, session_id=body.session_id)
    except Exception as exc:
        raise_curate_http_error(exc, action="save")
