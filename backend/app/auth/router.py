"""Authentication routes."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.spotify_oauth import (
    build_auth_url,
    exchange_code,
    generate_state,
    validate_state,
)
from app.auth.user import fetch_and_save_user_profile, save_user_profile, user_to_dict
from app.config import get_settings
from app.db import (
    SessionLocal,
    TasteProfileRecord,
    TokenRecord,
    UserRecord,
)
from app.spotify_client import call_spotify, create_spotify_client, get_spotify_client
from app.taste.engine import build_taste_profile, load_cached_taste_profile

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
SESSION_HOURS = 24 * 7


class MeResponse(BaseModel):
    """Current session and connected Spotify account."""

    connected: bool
    user_id: str
    display_name: str | None = None
    email: str | None = None
    image_url: str | None = None
    connected_at: str | None = None
    has_taste_profile: bool = False
    taste_updated_at: str | None = None


class AccountResponse(BaseModel):
    """Account dashboard payload."""

    user: dict[str, Any] | None
    has_taste_profile: bool
    taste_updated_at: str | None
    data_storage: dict[str, Any]


def get_db() -> Iterator[Session]:
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_session_token(*, user_id: str) -> str:
    """Create a signed session JWT."""
    settings = get_settings()
    payload = {
        "sub": user_id,
        "exp": datetime.now(UTC) + timedelta(hours=SESSION_HOURS),
    }
    return cast(str, jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM))


def get_current_user(request: Request) -> str:
    """Validate session cookie and return user id."""
    settings = get_settings()
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid session")
        return str(sub)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc


def _taste_metadata(db: Session) -> tuple[bool, str | None]:
    record = db.get(TasteProfileRecord, 1)
    if record is None:
        return False, None
    return True, record.updated_at.isoformat()


def _build_me_response(db: Session, *, user_id: str) -> MeResponse:
    user = db.get(UserRecord, 1)
    has_taste, taste_updated_at = _taste_metadata(db)
    return MeResponse(
        connected=True,
        user_id=user_id,
        display_name=user.display_name if user else None,
        email=user.email if user else None,
        image_url=user.image_url if user else None,
        connected_at=user.connected_at.isoformat() if user else None,
        has_taste_profile=has_taste,
        taste_updated_at=taste_updated_at,
    )


def _warm_taste_profile_after_login() -> None:
    """Build taste profile in the background when none exists yet."""
    db = SessionLocal()
    try:
        if load_cached_taste_profile(db) is not None:
            return
        token = db.get(TokenRecord, 1)
        if token is None:
            return
        sp = create_spotify_client(token.access_token)
        build_taste_profile(sp, db=db, force_refresh=False)
        logger.info("Generated taste profile after login")
    except Exception:
        logger.exception("Failed to generate taste profile after login")
    finally:
        db.close()


def _clear_connected_account(db: Session) -> None:
    """Remove stored credentials and profile data for account switching."""
    for model in (TokenRecord, UserRecord, TasteProfileRecord):
        record = db.get(model, 1)
        if record is not None:
            db.delete(record)
    db.commit()


@router.get("/login")
async def login() -> RedirectResponse:
    """Redirect to Spotify authorization."""
    state = generate_state()
    return RedirectResponse(build_auth_url(state=state))


@router.get("/callback")
async def callback(
    background_tasks: BackgroundTasks,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Handle Spotify OAuth callback."""
    settings = get_settings()
    if error:
        return RedirectResponse(f"{settings.frontend_url}/?error={error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    if not validate_state(state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    token_data = await exchange_code(code=code)
    expires_in = token_data.get("expires_in", 3600)
    if not isinstance(expires_in, (int, float)):
        expires_in = 3600
    expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))

    record = db.get(TokenRecord, 1)
    if record is None:
        record = TokenRecord(id=1)
        db.add(record)
    record.access_token = str(token_data["access_token"])
    refresh = token_data.get("refresh_token")
    if refresh:
        record.refresh_token = str(refresh)
    record.expires_at = expires_at
    record.scope = str(token_data.get("scope", ""))
    db.commit()

    user_record = fetch_and_save_user_profile(
        db,
        access_token=str(token_data["access_token"]),
    )
    session_token = create_session_token(user_id=user_record.spotify_id)
    background_tasks.add_task(_warm_taste_profile_after_login)

    response = RedirectResponse(f"{settings.frontend_url}/?login=1")
    response.set_cookie(
        "session",
        session_token,
        httponly=True,
        max_age=SESSION_HOURS * 3600,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/me", response_model=MeResponse)
async def me(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    """Return current authenticated user and profile status."""
    user = db.get(UserRecord, 1)
    if user is None and db.get(TokenRecord, 1) is not None:
        sp = await get_spotify_client(db)
        profile = await call_spotify(sp.me)
        save_user_profile(db, profile=profile)
    return _build_me_response(db, user_id=user_id)


@router.get("/account", response_model=AccountResponse)
def account(
    _user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Return account dashboard details and storage overview."""
    has_taste, taste_updated_at = _taste_metadata(db)
    settings = get_settings()
    return AccountResponse(
        user=user_to_dict(db.get(UserRecord, 1)),
        has_taste_profile=has_taste,
        taste_updated_at=taste_updated_at,
        data_storage={
            "database": settings.database_url.split("://", 1)[0],
            "description": (
                "This app stores one Spotify account at a time in a local database "
                "on the server. Logging out clears tokens and your taste profile so "
                "another account can connect."
            ),
            "stored_data": [
                {
                    "key": "tokens",
                    "description": "Spotify OAuth access and refresh tokens",
                },
                {
                    "key": "users",
                    "description": "Connected Spotify profile (name, email, avatar)",
                },
                {
                    "key": "taste_profiles",
                    "description": (
                        "AI-generated taste profile from your listening history"
                    ),
                },
                {
                    "key": "curate_sessions",
                    "description": "Mood concierge interviews and playlist drafts",
                },
                {
                    "key": "discover_runs",
                    "description": "History of auto-discovery playlist runs",
                },
                {
                    "key": "cleanup_runs",
                    "description": "Log of cleanup actions applied to playlists",
                },
            ],
        },
    )


@router.post("/logout")
def logout(db: Session = Depends(get_db)) -> JSONResponse:
    """Clear session and stored account data."""
    _clear_connected_account(db)
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie("session", httponly=True, samesite="lax", path="/")
    return response
