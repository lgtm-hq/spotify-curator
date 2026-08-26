"""AI health check routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.ai.config import load_ai_config
from app.ai.doctor import run_doctor
from app.auth.router import get_current_user

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/doctor")
def ai_doctor(_user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Run AI setup checks."""
    ai_config = load_ai_config()
    return {"checks": run_doctor(ai_config)}
