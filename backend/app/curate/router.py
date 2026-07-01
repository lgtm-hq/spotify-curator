"""Curate API routes."""

from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.router import get_current_user, get_db
from app.curate.prompt_engine import (
    answer_session,
    build_playlist_from_brief,
    save_playlist_to_spotify,
    start_session,
)
from app.spotify_client import get_spotify_client
from app.taste.engine import build_taste_profile

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
) -> dict:
    """Start mood concierge interview."""
    sp = await get_spotify_client(db)
    taste = build_taste_profile(sp, db=db)
    return start_session(db=db, taste_profile=taste)


@router.post("/answer")
async def curate_answer(
    body: AnswerRequest,
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Answer interview question."""
    sp = await get_spotify_client(db)
    taste = build_taste_profile(sp, db=db)
    try:
        return answer_session(
            db=db,
            session_id=body.session_id,
            answer=body.answer,
            taste_profile=taste,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/build")
async def curate_build(
    body: BuildRequest,
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Build playlist from interview brief."""
    sp = await get_spotify_client(db)
    taste = build_taste_profile(sp, db=db)
    try:
        return build_playlist_from_brief(
            sp=sp,
            db=db,
            session_id=body.session_id,
            taste_profile=taste,
            feedback=body.feedback,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/save")
async def curate_save(
    body: SaveRequest,
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Save curated playlist to Spotify."""
    sp = await get_spotify_client(db)
    try:
        return save_playlist_to_spotify(sp=sp, db=db, session_id=body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
