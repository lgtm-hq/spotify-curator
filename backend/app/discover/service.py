"""Auto-discovery playlist generation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, cast

import spotipy
import yaml
from sqlalchemy.orm import Session

from app.ai.budget import CostBudget
from app.ai.cli_schemas import discover_schema
from app.ai.config import get_provider, load_ai_config
from app.ai.invoke import call_ai
from app.ai.json_response import load_json_object
from app.ai.prompts.discover import DISCOVER_SYSTEM, DISCOVER_USER_TEMPLATE
from app.config import DEFAULT_CONFIG_FILE
from app.db import DiscoverRunRecord, dumps_json, utcnow
from app.spotify_candidates import get_recommendation_candidates
from app.taste.engine import build_taste_profile
from app.taste.models import TasteProfile


def _load_discover_config() -> dict[str, Any]:
    try:
        with DEFAULT_CONFIG_FILE.open() as f:
            data = yaml.safe_load(f) or {}
        return cast(dict[str, Any], data.get("discover", {}))
    except FileNotFoundError:
        return {}


def generate_discovery_playlist(
    sp: spotipy.Spotify,
    *,
    db: Session,
    taste_profile: TasteProfile | None = None,
) -> dict[str, Any]:
    """Generate a discovery playlist."""
    if taste_profile is None:
        taste_profile = build_taste_profile(sp, db=db)

    candidates = get_recommendation_candidates(sp, taste_profile, limit=50)

    discover_cfg = _load_discover_config()
    prefix = discover_cfg.get("playlist_name_prefix", "Discover Weekly")
    week = datetime.now().strftime("%Y-%m-%d")

    ai_config = load_ai_config()
    if ai_config.enabled and candidates:
        provider = get_provider(ai_config)
        budget = CostBudget(max_cost_usd=ai_config.max_cost_usd)
        prompt = DISCOVER_USER_TEMPLATE.format(
            taste_profile=taste_profile.model_dump_json(),
            candidates=json.dumps(candidates),
        )
        cli_schema = (
            discover_schema()
            if ai_config.transport and ai_config.transport.value == "cli"
            else None
        )
        response = call_ai(
            provider=provider,
            ai_config=ai_config,
            user_prompt=prompt,
            system_prompt=DISCOVER_SYSTEM,
            budget=budget,
            cli_schema=cli_schema,
        )
        parsed = load_json_object(content=response.content)
        selected_ids = set(parsed.get("selected_track_ids", []))
        uris = [c["uri"] for c in candidates if c["id"] in selected_ids]
        if not uris:
            uris = [c["uri"] for c in candidates[:20]]
        name = parsed.get("name", f"{prefix} — {week}")
        description = parsed.get("description", "Auto-generated discovery playlist")
        reasoning = parsed.get("reasoning", "")
    else:
        uris = [c["uri"] for c in candidates[:20]]
        name = f"{prefix} — {week}"
        description = "Auto-generated from Spotify recommendations"
        reasoning = "AI disabled — used top recommendations"

    me = sp.me()
    playlist = sp.user_playlist_create(
        me["id"],
        name,
        public=False,
        description=description,
    )
    for i in range(0, len(uris), 100):
        sp.playlist_add_items(playlist["id"], uris[i : i + 100])

    run_id = str(uuid.uuid4())
    record = DiscoverRunRecord(
        id=run_id,
        playlist_id=playlist["id"],
        playlist_name=name,
        tracks_json=dumps_json({"uris": uris, "reasoning": reasoning}),
        created_at=utcnow(),
    )
    db.add(record)
    db.commit()

    return {
        "run_id": run_id,
        "playlist_id": playlist["id"],
        "name": name,
        "track_count": len(uris),
        "reasoning": reasoning,
    }
