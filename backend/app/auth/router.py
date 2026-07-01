"""Authentication routes."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.auth.spotify_oauth import (
    build_auth_url,
    exchange_code,
    generate_state,
    validate_state,
)
from app.config import get_settings
from app.db import SessionLocal, TokenRecord

router = APIRouter(prefix="/auth", tags=["auth"])

ALGORITHM = "HS256"
SESSION_HOURS = 24 * 7


def get_db() -> Iterator[Session]:
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_session_token(*, user_id: str = "me") -> str:
    """Create a signed session JWT."""
    settings = get_settings()
    payload = {
        "sub": user_id,
        "exp": datetime.now(UTC) + timedelta(hours=SESSION_HOURS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


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


@router.get("/login")
async def login() -> RedirectResponse:
    """Redirect to Spotify authorization."""
    state = generate_state()
    response = RedirectResponse(build_auth_url(state=state))
    response.set_cookie(
        "oauth_state",
        state,
        httponly=True,
        max_age=600,
        samesite="lax",
    )
    return response


@router.get("/callback")
async def callback(
    request: Request,
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

    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or cookie_state != state or not validate_state(state):
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

    session_token = create_session_token()
    response = RedirectResponse(f"{settings.frontend_url}/")
    response.set_cookie(
        "session",
        session_token,
        httponly=True,
        max_age=SESSION_HOURS * 3600,
        samesite="lax",
    )
    response.delete_cookie("oauth_state")
    return response


@router.get("/me")
def me(user_id: str = Depends(get_current_user)) -> dict[str, str]:
    """Return current authenticated user."""
    return {"user_id": user_id}


@router.post("/logout")
def logout() -> JSONResponse:
    """Clear session cookie."""
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie("session", httponly=True, samesite="lax")
    return response
