"""Taste profile engine."""

from __future__ import annotations

import json
import logging
from typing import Any

import spotipy
from sqlalchemy.orm import Session

from app.ai.budget import CostBudget
from app.ai.cli_schemas import taste_profile_schema
from app.ai.config import get_provider, load_ai_config
from app.ai.invoke import call_ai
from app.ai.json_response import load_json_object
from app.ai.prompts.taste import TASTE_SYSTEM, TASTE_USER_TEMPLATE
from app.db import TasteProfileRecord, dumps_json, utcnow
from app.spotify_client import paginate
from app.taste.models import TasteProfile


def _avg_features(sp: spotipy.Spotify, track_ids: list[str]) -> dict[str, float]:
    """Compute average audio features for tracks."""
    totals: dict[str, float] = {}
    count = 0
    for i in range(0, len(track_ids), 100):
        batch = track_ids[i : i + 100]
        try:
            feats = sp.audio_features(batch) or []
        except Exception as exc:
            logging.debug("audio_features unavailable for batch: %s", exc)
            continue
        for feat in feats:
            if not feat:
                continue
            count += 1
            for key in ("energy", "valence", "danceability", "tempo"):
                totals[key] = totals.get(key, 0.0) + float(feat.get(key, 0))
    if count == 0:
        return {}
    return {k: round(v / count, 3) for k, v in totals.items()}


def _collect_listening_data(sp: spotipy.Spotify) -> dict[str, Any]:
    """Collect raw listening data from Spotify."""
    top_artists_short = sp.current_user_top_artists(limit=20, time_range="short_term")
    top_artists_medium = sp.current_user_top_artists(limit=20, time_range="medium_term")
    top_tracks = sp.current_user_top_tracks(limit=50, time_range="medium_term")
    saved = paginate(sp, "current_user_saved_tracks", limit=50)[:50]

    genres: set[str] = set()
    for artist in top_artists_short.get("items", []) + top_artists_medium.get(
        "items",
        [],
    ):
        for genre in artist.get("genres", []):
            genres.add(genre)

    top_artist_ids = [
        a["id"] for a in top_artists_medium.get("items", []) if a.get("id")
    ]
    top_track_ids = [t["id"] for t in top_tracks.get("items", []) if t.get("id")]
    audio_features = _avg_features(sp, top_track_ids)

    return {
        "top_artists": [
            {"name": a.get("name"), "genres": a.get("genres", [])}
            for a in top_artists_medium.get("items", [])
        ],
        "top_tracks": [
            {
                "name": t.get("name"),
                "artists": [x["name"] for x in t.get("artists", [])],
            }
            for t in top_tracks.get("items", [])
        ],
        "saved_tracks": [
            {
                "name": (item.get("track") or {}).get("name"),
                "artists": [
                    a["name"] for a in (item.get("track") or {}).get("artists", [])
                ],
            }
            for item in saved
        ],
        "audio_features": audio_features,
        "top_artist_ids": top_artist_ids,
        "top_track_ids": top_track_ids,
        "seed_genres": sorted(genres)[:5],
    }


def build_taste_profile(
    sp: spotipy.Spotify,
    *,
    db: Session,
    force_refresh: bool = False,
) -> TasteProfile:
    """Build or load cached taste profile."""
    if not force_refresh:
        record = db.get(TasteProfileRecord, 1)
        if record is not None:
            data = json.loads(record.profile_json)
            return TasteProfile.model_validate(data)

    data = _collect_listening_data(sp)
    ai_config = load_ai_config()

    if ai_config.enabled:
        provider = get_provider(ai_config)
        budget = CostBudget(max_cost_usd=ai_config.max_cost_usd)
        prompt = TASTE_USER_TEMPLATE.format(
            top_artists=json.dumps(data["top_artists"][:15]),
            top_tracks=json.dumps(data["top_tracks"][:20]),
            saved_tracks=json.dumps(data["saved_tracks"][:15]),
            audio_features=json.dumps(data["audio_features"]),
        )
        cli_schema = (
            taste_profile_schema()
            if ai_config.transport and ai_config.transport.value == "cli"
            else None
        )
        response = call_ai(
            provider=provider,
            ai_config=ai_config,
            user_prompt=prompt,
            system_prompt=TASTE_SYSTEM,
            budget=budget,
            cli_schema=cli_schema,
        )
        parsed = load_json_object(content=response.content)
        profile = TasteProfile(
            summary=parsed.get("summary", ""),
            genres=parsed.get("genres", data["seed_genres"]),
            mood_tags=parsed.get("mood_tags", []),
            era_preference=parsed.get("era_preference", ""),
            energy_range=parsed.get("energy_range", ""),
            top_artist_ids=data["top_artist_ids"],
            top_track_ids=data["top_track_ids"],
            seed_genres=data["seed_genres"],
        )
    else:
        profile = TasteProfile(
            summary="Based on your top artists and tracks.",
            genres=data["seed_genres"],
            mood_tags=["mixed"],
            top_artist_ids=data["top_artist_ids"],
            top_track_ids=data["top_track_ids"],
            seed_genres=data["seed_genres"],
        )

    record = db.get(TasteProfileRecord, 1)
    if record is None:
        record = TasteProfileRecord(id=1)
        db.add(record)
    record.profile_json = dumps_json(profile.model_dump())
    record.updated_at = utcnow()
    db.commit()
    return profile
