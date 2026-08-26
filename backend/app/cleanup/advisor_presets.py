"""Built-in and user-saved AI advisor presets."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.cleanup.suggest_options import CleanupSuggestOptions
from app.db import AdvisorPresetRecord, dumps_json, loads_json, utcnow

BUILTIN_QUICK_STARTS: list[dict[str, Any]] = [
    {
        "id": "full-audit",
        "name": "Full library audit",
        "description": "Balanced overview — rank the cleanups worth doing first.",
        "kind": "intent",
        "builtin": True,
        "ai_context": (
            "Give a balanced library-wide audit. "
            "Rank suggestions by impact and effort, "
            "using the user's taste profile to prioritize playlists they actually use."
        ),
    },
    {
        "id": "quick-dupes",
        "name": "Quick dupes pass",
        "description": "Lean into duplicate removal and fast, obvious wins.",
        "kind": "intent",
        "builtin": True,
        "ai_context": (
            "Prioritize duplicate tracks and quick dedupe wins. Deprioritize subtle "
            "organizational suggestions unless duplicates are exhausted."
        ),
    },
    {
        "id": "weekend-deep-clean",
        "name": "Weekend deep clean",
        "description": "High-impact cleanups that are worth a longer session.",
        "kind": "intent",
        "builtin": True,
        "ai_context": (
            "Prioritize high-impact cleanups. Flag bloated playlists and duplicates "
            "that waste the most listening time. Favor fewer, stronger suggestions."
        ),
    },
    {
        "id": "stale-only",
        "name": "Maintenance mode",
        "description": "Playlists that probably need attention after being neglected.",
        "kind": "intent",
        "builtin": True,
        "ai_context": (
            "Focus on playlists that look neglected or outdated. "
            "Suggest refreshes where "
            "scan data is old or the playlist seems unmaintained."
        ),
    },
]


def quick_start_context(quick_start_id: str | None) -> str:
    """Return AI guidance text for a built-in quick start selection."""
    if not quick_start_id:
        return ""
    for preset in BUILTIN_QUICK_STARTS:
        if preset["id"] == quick_start_id:
            return str(preset.get("ai_context") or "")
    return ""


def list_presets(db: Session) -> list[dict[str, Any]]:
    """Return built-in quick starts plus user-saved configuration presets."""
    presets = [dict(item) for item in BUILTIN_QUICK_STARTS]
    records = db.query(AdvisorPresetRecord).order_by(AdvisorPresetRecord.name).all()
    for record in records:
        presets.append(
            {
                "id": record.id,
                "name": record.name,
                "description": record.description or "Saved scan configuration",
                "kind": "configuration",
                "builtin": False,
                "options": loads_json(record.options_json),
                "created_at": _iso(record.created_at),
                "updated_at": _iso(record.updated_at),
            },
        )
    return presets


def save_preset(
    db: Session,
    *,
    name: str,
    options: CleanupSuggestOptions,
    description: str = "",
) -> dict[str, Any]:
    """Persist a user-defined scan configuration preset."""
    preset_id = str(uuid.uuid4())
    now = utcnow()
    payload = options.model_dump()
    payload.pop("quick_start_id", None)
    record = AdvisorPresetRecord(
        id=preset_id,
        name=name.strip(),
        description=description.strip(),
        options_json=dumps_json(payload),
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.commit()
    return {
        "id": preset_id,
        "name": record.name,
        "description": record.description,
        "kind": "configuration",
        "builtin": False,
        "options": loads_json(record.options_json),
        "created_at": _iso(record.created_at),
        "updated_at": _iso(record.updated_at),
    }


def delete_preset(db: Session, preset_id: str) -> bool:
    """Delete a user preset. Built-ins cannot be deleted."""
    if any(item["id"] == preset_id for item in BUILTIN_QUICK_STARTS):
        return False
    record = db.get(AdvisorPresetRecord, preset_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True


def _iso(value: datetime) -> str:
    return value.isoformat()
