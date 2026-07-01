"""Taste profile API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.router import get_current_user, get_db
from app.spotify_client import get_spotify_client
from app.taste.engine import build_taste_profile
from app.taste.models import TasteProfile

router = APIRouter(prefix="/taste", tags=["taste"])


@router.get("", response_model=TasteProfile)
async def get_taste_profile(
    refresh: bool = Query(default=False),
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TasteProfile:
    """Get or refresh taste profile."""
    sp = await get_spotify_client(db)
    return build_taste_profile(sp, db=db, force_refresh=refresh)


@router.post("/refresh", response_model=TasteProfile)
async def refresh_taste_profile(
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TasteProfile:
    """Regenerate taste profile from current listening data."""
    sp = await get_spotify_client(db)
    return build_taste_profile(sp, db=db, force_refresh=True)
