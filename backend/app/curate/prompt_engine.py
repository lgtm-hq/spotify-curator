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
from app.spotify_candidates import get_recommendation_candidates
from app.taste.engine import compact_taste_for_prompt
from app.taste.models import TasteProfile
from app.track_metadata import enrich_track_uris

MAX_ROUNDS = 5
MIN_PLAYLIST_TRACKS = 20
MAX_PLAYLIST_TRACKS = 35
CANDIDATE_POOL_LIMIT = 80
INTERVIEW_MAX_TOKENS = 1024
PLAYLIST_BUILD_MAX_TOKENS = 3072


def _dedupe_uris(uris: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for uri in uris:
        if not isinstance(uri, str) or not uri.strip() or uri in seen:
            continue
        seen.add(uri)
        ordered.append(uri)
    return ordered


def _normalize_playlist_uris(
    parsed: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    previous_uris: list[str] | None = None,
) -> list[str]:
    """Ensure the playlist meets minimum length using the candidate pool."""
    raw_uris = parsed.get("track_uris", [])
    uris = _dedupe_uris([uri for uri in raw_uris if isinstance(uri, str)])

    candidate_uris = [
        str(candidate["uri"])
        for candidate in candidates
        if isinstance(candidate.get("uri"), str)
    ]
    allowed = set(candidate_uris)
    if previous_uris:
        allowed.update(previous_uris)

    uris = [uri for uri in uris if uri in allowed]
    if not uris and previous_uris:
        uris = _dedupe_uris(previous_uris)

    seen = set(uris)
    if len(uris) < MIN_PLAYLIST_TRACKS:
        for uri in candidate_uris:
            if uri in seen:
                continue
            uris.append(uri)
            seen.add(uri)
            if len(uris) >= MIN_PLAYLIST_TRACKS:
                break

    return uris[:MAX_PLAYLIST_TRACKS]


def _format_conversation(messages: list[dict[str, Any]]) -> str:
    lines = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines) or "(none)"


def _compact_candidates(candidates: list[dict[str, Any]], *, limit: int = 60) -> str:
    """Trim candidate payload for playlist-build prompts."""
    compact = [
        {
            "id": candidate.get("id"),
            "name": candidate.get("name"),
            "artists": (candidate.get("artists") or [])[:3],
            "uri": candidate.get("uri"),
        }
        for candidate in candidates[:limit]
        if candidate.get("id") and candidate.get("uri")
    ]
    return json.dumps(compact, separators=(",", ":"))


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
        taste_profile=compact_taste_for_prompt(taste_profile),
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
        max_tokens=INTERVIEW_MAX_TOKENS,
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
        taste_profile=compact_taste_for_prompt(taste_profile),
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
        max_tokens=INTERVIEW_MAX_TOKENS,
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

    candidates = get_recommendation_candidates(
        sp,
        taste_profile,
        limit=CANDIDATE_POOL_LIMIT,
    )

    if not candidates:
        msg = "Could not find candidate tracks to build a playlist"
        raise ValueError(msg)

    previous_uris: list[str] | None = None
    if record.proposed_tracks_json:
        existing = loads_json(record.proposed_tracks_json)
        if isinstance(existing, dict):
            raw_previous = existing.get("track_uris", [])
            if isinstance(raw_previous, list):
                previous_uris = [
                    str(uri) for uri in raw_previous if isinstance(uri, str)
                ]

    ai_config = load_ai_config()
    if ai_config.enabled and candidates:
        provider = get_provider(ai_config)
        budget = CostBudget(max_cost_usd=ai_config.max_cost_usd)
        candidate_payload = _compact_candidates(candidates)
        if feedback and record.proposed_tracks_json:
            prompt = REFINE_TEMPLATE.format(
                brief=record.playlist_brief,
                taste_profile=compact_taste_for_prompt(taste_profile),
                candidates=candidate_payload,
                current=record.proposed_tracks_json,
                feedback=feedback,
            )
        else:
            prompt = PLAYLIST_BUILD_TEMPLATE.format(
                brief=record.playlist_brief,
                taste_profile=compact_taste_for_prompt(taste_profile),
                candidates=candidate_payload,
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
            max_tokens=PLAYLIST_BUILD_MAX_TOKENS,
            cli_schema=cli_schema,
        )
        parsed = load_json_object(content=response.content)
    else:
        selected = candidates[:MIN_PLAYLIST_TRACKS]
        parsed = {
            "name": "Mood Mix",
            "description": record.playlist_brief,
            "track_uris": [t["uri"] for t in selected],
            "reasoning": "Selected top recommendations matching taste seeds.",
        }

    normalized_uris = _normalize_playlist_uris(
        parsed,
        candidates,
        previous_uris=previous_uris,
    )
    parsed["track_uris"] = normalized_uris
    parsed["tracks"] = enrich_track_uris(
        sp,
        normalized_uris,
        candidates=candidates,
    )
    if len(parsed["tracks"]) < MIN_PLAYLIST_TRACKS:
        present = {track["uri"] for track in parsed["tracks"]}
        for candidate in candidates:
            uri = candidate.get("uri")
            if not isinstance(uri, str) or uri in present:
                continue
            parsed["tracks"].append(
                {
                    "id": candidate.get("id", ""),
                    "uri": uri,
                    "name": candidate.get("name", "Unknown"),
                    "artists": candidate.get("artists", []),
                    "album": candidate.get("album"),
                    "duration_ms": candidate.get("duration_ms", 0),
                    "image_url": candidate.get("image_url"),
                    "preview_url": candidate.get("preview_url"),
                    "explicit": candidate.get("explicit", False),
                },
            )
            present.add(uri)
            if len(parsed["tracks"]) >= MIN_PLAYLIST_TRACKS:
                break
    parsed["track_uris"] = [track["uri"] for track in parsed["tracks"]][
        :MAX_PLAYLIST_TRACKS
    ]
    parsed["tracks"] = parsed["tracks"][:MAX_PLAYLIST_TRACKS]

    if feedback:
        messages = loads_json(record.conversation_json)
        if isinstance(messages, list):
            messages.append({"role": "user", "content": feedback})
            messages.append(
                {
                    "role": "assistant",
                    "content": "Updated the playlist based on your feedback.",
                },
            )
            record.conversation_json = dumps_json(messages)

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
    track_uris: list[str] | None = None,
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

    uris = track_uris or proposal.get("track_uris", [])
    if not uris:
        msg = "No tracks to save"
        raise ValueError(msg)

    playlist = sp.current_user_playlist_create(
        proposal.get("name", "Mood Mix"),
        public=False,
        description=proposal.get("description", ""),
    )
    for i in range(0, len(uris), 100):
        sp.playlist_add_items(playlist["id"], uris[i : i + 100])

    record.status = "saved"
    record.spotify_playlist_id = str(playlist["id"])
    record.updated_at = utcnow()
    db.commit()
    return {
        "playlist_id": playlist["id"],
        "name": playlist["name"],
        "tracks": len(uris),
    }
