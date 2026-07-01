"""Mood concierge prompt engine."""

from __future__ import annotations

import json
import uuid
from typing import Any

import spotipy
from sqlalchemy.orm import Session

from app.ai.budget import CostBudget
from app.ai.cli_schemas import curate_playlist_schema, curate_question_schema
from app.ai.config import get_provider, load_ai_config
from app.ai.invoke import call_ai
from app.ai.json_response import load_json_object
from app.ai.prompts.curate import (
    CURATE_SYSTEM,
    CURATE_USER_TEMPLATE,
    PLAYLIST_BUILD_TEMPLATE,
    REFINE_TEMPLATE,
)
from app.db import CurateSessionRecord, dumps_json, loads_json, utcnow
from app.taste.models import TasteProfile

MAX_ROUNDS = 5


def _format_conversation(messages: list[dict[str, Any]]) -> str:
    lines = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines) or "(none)"


def start_session(*, db: Session, taste_profile: TasteProfile) -> dict[str, Any]:
    """Start a new mood concierge session."""
    ai_config = load_ai_config()
    if not ai_config.enabled:
        session_id = str(uuid.uuid4())
        messages = [
            {
                "role": "assistant",
                "content": "What kind of vibe are you in the mood for?",
            },
        ]
        record = CurateSessionRecord(
            id=session_id,
            conversation_json=dumps_json(messages),
            status="active",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(record)
        db.commit()
        return {
            "session_id": session_id,
            "done": False,
            "question": "What kind of vibe are you in the mood for?",
            "options": ["Chill", "Energetic", "Melancholy", "Focus", "Party"],
        }

    provider = get_provider(ai_config)
    budget = CostBudget(max_cost_usd=ai_config.max_cost_usd)
    prompt = CURATE_USER_TEMPLATE.format(
        taste_profile=taste_profile.model_dump_json(),
        conversation="(starting interview)",
    )
    cli_schema = (
        curate_question_schema()
        if ai_config.transport and ai_config.transport.value == "cli"
        else None
    )
    response = call_ai(
        provider=provider,
        ai_config=ai_config,
        user_prompt=prompt,
        system_prompt=CURATE_SYSTEM,
        budget=budget,
        cli_schema=cli_schema,
    )
    parsed = load_json_object(content=response.content)

    session_id = str(uuid.uuid4())
    messages = [{"role": "assistant", "content": parsed.get("question", "")}]
    record = CurateSessionRecord(
        id=session_id,
        conversation_json=dumps_json(messages),
        playlist_brief=parsed.get("playlist_brief"),
        status="active" if not parsed.get("done") else "brief_ready",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(record)
    db.commit()
    return {"session_id": session_id, **parsed}


def answer_session(
    *,
    db: Session,
    session_id: str,
    answer: str,
    taste_profile: TasteProfile,
) -> dict[str, Any]:
    """Process user answer and return next question or brief."""
    record = db.get(CurateSessionRecord, session_id)
    if record is None:
        msg = "Session not found"
        raise ValueError(msg)

    messages = loads_json(record.conversation_json)
    if not isinstance(messages, list):
        messages = []
    messages.append({"role": "user", "content": answer})

    ai_config = load_ai_config()
    if not ai_config.enabled:
        if len([m for m in messages if m.get("role") == "user"]) >= 3:
            record.playlist_brief = f"Mood playlist based on: {answer}"
            record.status = "brief_ready"
            record.updated_at = utcnow()
            db.commit()
            return {
                "session_id": session_id,
                "done": True,
                "playlist_brief": record.playlist_brief,
            }
        record.conversation_json = dumps_json(messages)
        record.updated_at = utcnow()
        db.commit()
        return {
            "session_id": session_id,
            "done": False,
            "question": "Tell me more — what activity is this for?",
            "options": ["Working", "Driving", "Cooking", "Gym", "Relaxing"],
        }

    provider = get_provider(ai_config)
    budget = CostBudget(max_cost_usd=ai_config.max_cost_usd)
    prompt = CURATE_USER_TEMPLATE.format(
        taste_profile=taste_profile.model_dump_json(),
        conversation=_format_conversation(messages),
    )
    cli_schema = (
        curate_question_schema()
        if ai_config.transport and ai_config.transport.value == "cli"
        else None
    )
    response = call_ai(
        provider=provider,
        ai_config=ai_config,
        user_prompt=prompt,
        system_prompt=CURATE_SYSTEM,
        budget=budget,
        cli_schema=cli_schema,
    )
    parsed = load_json_object(content=response.content)

    if parsed.get("question"):
        messages.append({"role": "assistant", "content": parsed["question"]})
    record.conversation_json = dumps_json(messages)
    record.updated_at = utcnow()

    user_rounds = len([m for m in messages if m.get("role") == "user"])
    if parsed.get("done") or user_rounds >= MAX_ROUNDS:
        record.playlist_brief = (
            parsed.get("playlist_brief")
            or f"Curated mood: {_format_conversation(messages)}"
        )
        record.status = "brief_ready"
        parsed["done"] = True
        parsed["playlist_brief"] = record.playlist_brief

    db.commit()
    return {"session_id": session_id, **parsed}


def build_playlist_from_brief(
    *,
    sp: spotipy.Spotify,
    db: Session,
    session_id: str,
    taste_profile: TasteProfile,
    feedback: str | None = None,
) -> dict[str, Any]:
    """Build playlist from session brief using Spotify recs + AI."""
    record = db.get(CurateSessionRecord, session_id)
    if record is None or not record.playlist_brief:
        msg = "Session not ready for playlist build"
        raise ValueError(msg)

    seeds: dict[str, Any] = {}
    if taste_profile.top_track_ids:
        seeds["seed_tracks"] = taste_profile.top_track_ids[:2]
    if taste_profile.top_artist_ids:
        seeds["seed_artists"] = taste_profile.top_artist_ids[:2]
    if taste_profile.seed_genres:
        seeds["seed_genres"] = taste_profile.seed_genres[:1]

    recs = sp.recommendations(limit=50, **seeds) if seeds else {"tracks": []}
    candidates = [
        {
            "id": t["id"],
            "uri": t["uri"],
            "name": t["name"],
            "artists": [a["name"] for a in t.get("artists", [])],
        }
        for t in recs.get("tracks", [])
    ]

    ai_config = load_ai_config()
    if ai_config.enabled and candidates:
        provider = get_provider(ai_config)
        budget = CostBudget(max_cost_usd=ai_config.max_cost_usd)
        if feedback and record.proposed_tracks_json:
            prompt = REFINE_TEMPLATE.format(
                current=record.proposed_tracks_json,
                feedback=feedback,
            )
        else:
            prompt = PLAYLIST_BUILD_TEMPLATE.format(
                brief=record.playlist_brief,
                taste_profile=taste_profile.model_dump_json(),
                candidates=json.dumps(candidates[:40]),
            )
        cli_schema = (
            curate_playlist_schema()
            if ai_config.transport and ai_config.transport.value == "cli"
            else None
        )
        response = call_ai(
            provider=provider,
            ai_config=ai_config,
            user_prompt=prompt,
            system_prompt=CURATE_SYSTEM,
            budget=budget,
            cli_schema=cli_schema,
        )
        parsed = load_json_object(content=response.content)
    else:
        selected = candidates[:20]
        parsed = {
            "name": "Mood Mix",
            "description": record.playlist_brief,
            "track_uris": [t["uri"] for t in selected],
            "reasoning": "Selected top recommendations matching taste seeds.",
        }

    record.proposed_tracks_json = dumps_json(parsed)
    record.status = "proposal_ready"
    record.updated_at = utcnow()
    db.commit()
    return parsed


def save_playlist_to_spotify(
    *,
    sp: spotipy.Spotify,
    db: Session,
    session_id: str,
) -> dict[str, Any]:
    """Create Spotify playlist from proposed tracks."""
    record = db.get(CurateSessionRecord, session_id)
    if record is None or not record.proposed_tracks_json:
        msg = "No proposed playlist to save"
        raise ValueError(msg)

    proposal = loads_json(record.proposed_tracks_json)
    if not isinstance(proposal, dict):
        msg = "Invalid proposal data"
        raise ValueError(msg)

    me = sp.me()
    playlist = sp.user_playlist_create(
        me["id"],
        proposal.get("name", "Mood Mix"),
        public=False,
        description=proposal.get("description", ""),
    )
    uris = proposal.get("track_uris", [])
    for i in range(0, len(uris), 100):
        sp.playlist_add_items(playlist["id"], uris[i : i + 100])

    record.status = "saved"
    record.updated_at = utcnow()
    db.commit()
    return {
        "playlist_id": playlist["id"],
        "name": playlist["name"],
        "tracks": len(uris),
    }
