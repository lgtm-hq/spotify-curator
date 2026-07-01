"""AI health check routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.ai.config import load_ai_config
from app.ai.doctor import run_doctor

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/doctor")
def ai_doctor() -> dict:
    """Run AI setup checks."""
    ai_config = load_ai_config()
    return {"checks": run_doctor(ai_config)}
