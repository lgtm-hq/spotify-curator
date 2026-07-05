"""Taste profile engine."""

from __future__ import annotations

import json
import logging
import statistics
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
from app.spotify_client import paginate, playlist_track_total
from app.taste.models import TasteLane, TasteProfile

logger = logging.getLogger(__name__)

_AUDIO_FEATURE_KEYS = (
    "energy",
    "valence",
    "danceability",
    "tempo",
    "acousticness",
    "instrumentalness",
    "speechiness",
)
_SUMMARY_MAX_CHARS = 600


def _artist_row(artist: dict[str, Any]) -> dict[str, Any]:
    """Serialize a Spotify artist for the taste prompt."""
    return {
        "name": artist.get("name"),
        "genres": artist.get("genres", [])[:5],
    }


def _track_row(track: dict[str, Any], *, include_year: bool = False) -> dict[str, Any]:
    """Serialize a Spotify track for the taste prompt."""
    row: dict[str, Any] = {
        "name": track.get("name"),
        "artists": [artist.get("name") for artist in track.get("artists", [])],
    }
    if include_year:
        release_date = (track.get("album") or {}).get("release_date", "")
        if release_date and release_date[:4].isdigit():
            row["year"] = int(release_date[:4])
    return row


def _saved_track_row(item: dict[str, Any]) -> dict[str, Any]:
    """Serialize a saved track entry."""
    track = item.get("track") or {}
    row = _track_row(track, include_year=True)
    if item.get("added_at"):
        row["added_at"] = item["added_at"]
    return row


def _recently_played_row(item: dict[str, Any]) -> dict[str, Any]:
    """Serialize a recently played entry."""
    track = item.get("track") or {}
    row = _track_row(track, include_year=True)
    if item.get("played_at"):
        row["played_at"] = item["played_at"]
    return row


def _release_year_summary(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize release years from medium-term top tracks."""
    years = [
        int(track["year"]) for track in tracks if isinstance(track.get("year"), int)
    ]
    if not years:
        return {}
    return {
        "min": min(years),
        "max": max(years),
        "median": int(statistics.median(years)),
        "sample_size": len(years),
    }


def _avg_features(
    sp: spotipy.Spotify,
    track_ids: list[str],
) -> tuple[dict[str, float], bool]:
    """Compute average audio features for tracks."""
    totals: dict[str, float] = {}
    count = 0
    for index in range(0, len(track_ids), 100):
        batch = track_ids[index : index + 100]
        try:
            feats = sp.audio_features(batch) or []
        except Exception as exc:
            logger.warning(
                "audio_features unavailable for taste profile batch: %s", exc
            )
            continue
        for feat in feats:
            if not feat:
                continue
            count += 1
            for key in _AUDIO_FEATURE_KEYS:
                totals[key] = totals.get(key, 0.0) + float(feat.get(key, 0))
    if count == 0:
        return {}, False
    return {key: round(value / count, 3) for key, value in totals.items()}, True


def _owned_playlist_rows(
    sp: spotipy.Spotify,
    *,
    current_user_id: str | None,
) -> list[dict[str, Any]]:
    """Collect owned playlist metadata for taste analysis."""
    if not current_user_id:
        return []
    playlists = paginate(sp, "current_user_playlists")
    owned: list[dict[str, Any]] = []
    for meta in playlists:
        owner = meta.get("owner") or {}
        if str(owner.get("id", "")) != current_user_id:
            continue
        description = str(meta.get("description") or "").strip()
        owned.append(
            {
                "name": meta.get("name"),
                "track_count": playlist_track_total(meta),
                "description": description[:120] if description else None,
            },
        )
    owned.sort(key=lambda row: int(row.get("track_count") or 0), reverse=True)
    return owned[:12]


def _collect_listening_data(sp: spotipy.Spotify) -> dict[str, Any]:
    """Collect raw listening data from Spotify."""
    me = sp.current_user() or {}
    current_user_id = me.get("id")

    top_artists_long = sp.current_user_top_artists(limit=20, time_range="long_term")
    top_artists_medium = sp.current_user_top_artists(limit=20, time_range="medium_term")
    top_artists_short = sp.current_user_top_artists(limit=20, time_range="short_term")
    top_tracks_long = sp.current_user_top_tracks(limit=50, time_range="long_term")
    top_tracks_medium = sp.current_user_top_tracks(limit=50, time_range="medium_term")
    recently_played = sp.current_user_recently_played(limit=50)
    saved = paginate(sp, "current_user_saved_tracks", limit=50)[:50]

    genres: set[str] = set()
    for artist in (
        top_artists_long.get("items", [])
        + top_artists_medium.get("items", [])
        + top_artists_short.get("items", [])
    ):
        for genre in artist.get("genres", []):
            genres.add(genre)

    medium_track_rows = [
        _track_row(track, include_year=True)
        for track in top_tracks_medium.get("items", [])
        if track.get("id")
    ]
    top_artist_ids = [
        artist["id"]
        for artist in top_artists_medium.get("items", [])
        if artist.get("id")
    ]
    top_track_ids = [
        track["id"] for track in top_tracks_medium.get("items", []) if track.get("id")
    ]
    audio_features, audio_features_available = _avg_features(sp, top_track_ids)

    return {
        "top_artists_long": [
            _artist_row(artist) for artist in top_artists_long.get("items", [])
        ],
        "top_artists_medium": [
            _artist_row(artist) for artist in top_artists_medium.get("items", [])
        ],
        "top_artists_short": [
            _artist_row(artist) for artist in top_artists_short.get("items", [])
        ],
        "top_tracks_long": [
            _track_row(track, include_year=True)
            for track in top_tracks_long.get("items", [])
        ],
        "top_tracks_medium": medium_track_rows,
        "recently_played": [
            _recently_played_row(item) for item in recently_played.get("items", [])
        ],
        "saved_tracks": [_saved_track_row(item) for item in saved],
        "owned_playlists": _owned_playlist_rows(sp, current_user_id=current_user_id),
        "release_years": _release_year_summary(medium_track_rows),
        "audio_features": audio_features,
        "audio_features_available": audio_features_available,
        "top_artist_ids": top_artist_ids,
        "top_track_ids": top_track_ids,
        "seed_genres": sorted(genres)[:5],
    }


def _normalize_summary(summary: str) -> str:
    """Keep summary concise for UI and downstream prompts."""
    text = summary.strip()
    if len(text) <= _SUMMARY_MAX_CHARS:
        return text
    clipped = text[: _SUMMARY_MAX_CHARS - 1].rsplit(" ", 1)[0]
    return f"{clipped}…"


def _normalize_lanes(raw_lanes: Any) -> list[TasteLane]:
    """Parse taste lanes from AI output."""
    if not isinstance(raw_lanes, list):
        return []
    lanes: list[TasteLane] = []
    for lane in raw_lanes[:4]:
        if not isinstance(lane, dict):
            continue
        label = str(lane.get("label") or "").strip()
        description = str(lane.get("description") or "").strip()
        if not label:
            continue
        artists = [
            str(name).strip() for name in lane.get("artists", []) if str(name).strip()
        ]
        lanes.append(
            TasteLane(
                label=label,
                description=description,
                artists=artists[:5],
            ),
        )
    return lanes


def _normalize_string_list(raw: Any, *, limit: int = 8) -> list[str]:
    """Parse a list of strings from AI output."""
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text:
            values.append(text)
    return values[:limit]


def _profile_from_ai(parsed: dict[str, Any], data: dict[str, Any]) -> TasteProfile:
    """Build a validated taste profile from AI JSON."""
    confidence = str(parsed.get("confidence") or "medium").lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"

    genres = _normalize_string_list(parsed.get("genres"), limit=12)
    if not genres:
        genres = data["seed_genres"]

    return TasteProfile(
        summary=_normalize_summary(str(parsed.get("summary") or "")),
        genres=genres,
        mood_tags=_normalize_string_list(parsed.get("mood_tags"), limit=6),
        era_preference=str(parsed.get("era_preference") or "").strip(),
        energy_range=str(parsed.get("energy_range") or "").strip(),
        taste_lanes=_normalize_lanes(parsed.get("taste_lanes")),
        core_taste=str(parsed.get("core_taste") or "").strip(),
        recent_shift=str(parsed.get("recent_shift") or "").strip(),
        curation_hints=_normalize_string_list(parsed.get("curation_hints"), limit=5),
        avoid=_normalize_string_list(parsed.get("avoid"), limit=6),
        confidence=confidence,
        audio_features_summary=str(parsed.get("audio_features_summary") or "").strip(),
        top_artist_ids=data["top_artist_ids"],
        top_track_ids=data["top_track_ids"],
        seed_genres=data["seed_genres"],
    )


def _fallback_profile(data: dict[str, Any]) -> TasteProfile:
    """Build a minimal profile when AI is disabled."""
    return TasteProfile(
        summary="Based on your long-term and recent listening patterns.",
        genres=data["seed_genres"],
        mood_tags=["mixed"],
        core_taste="Stable favorites from medium-term top artists and tracks.",
        recent_shift="none notable",
        curation_hints=[
            "Prefer tracks from your medium-term top artists.",
            "Keep energy aligned with your recent top tracks.",
        ],
        confidence="low",
        audio_features_summary=(
            "Audio features were averaged from medium-term top tracks."
            if data["audio_features_available"]
            else "Audio feature data was unavailable from Spotify."
        ),
        top_artist_ids=data["top_artist_ids"],
        top_track_ids=data["top_track_ids"],
        seed_genres=data["seed_genres"],
    )


def build_taste_profile(
    sp: spotipy.Spotify,
    *,
    db: Session,
    force_refresh: bool = False,
) -> TasteProfile:
    """Build or load cached taste profile."""
    cached = load_cached_taste_profile(db)
    if cached is not None and not force_refresh:
        return cached

    data = _collect_listening_data(sp)
    ai_config = load_ai_config()

    if ai_config.enabled:
        audio_features_note = (
            ""
            if data["audio_features_available"]
            else (
                "\nNote: Spotify audio feature data was unavailable; "
                "infer mood/energy from artist genres and track metadata."
            )
        )
        prompt = TASTE_USER_TEMPLATE.format(
            top_artists_long=json.dumps(data["top_artists_long"][:15]),
            top_artists_medium=json.dumps(data["top_artists_medium"][:15]),
            top_artists_short=json.dumps(data["top_artists_short"][:15]),
            top_tracks_long=json.dumps(data["top_tracks_long"][:20]),
            top_tracks_medium=json.dumps(data["top_tracks_medium"][:20]),
            recently_played=json.dumps(data["recently_played"][:20]),
            saved_tracks=json.dumps(data["saved_tracks"][:15]),
            owned_playlists=json.dumps(data["owned_playlists"]),
            release_years=json.dumps(data["release_years"]),
            audio_features=json.dumps(data["audio_features"]),
            audio_features_note=audio_features_note,
        )
        provider = get_provider(ai_config)
        budget = CostBudget(max_cost_usd=ai_config.max_cost_usd)
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
        profile = _profile_from_ai(parsed, data)
    else:
        profile = _fallback_profile(data)

    record = db.get(TasteProfileRecord, 1)
    if record is None:
        record = TasteProfileRecord(id=1)
        db.add(record)
    record.profile_json = dumps_json(profile.model_dump())
    record.updated_at = utcnow()
    db.commit()
    return profile


def load_cached_taste_profile(db: Session) -> TasteProfile | None:
    """Return cached taste profile when available."""
    record = db.get(TasteProfileRecord, 1)
    if record is None:
        return None
    data = json.loads(record.profile_json)
    return TasteProfile.model_validate(data)


def compact_taste_for_prompt(taste: TasteProfile) -> str:
    """Return a small taste JSON blob for fast interview prompts."""
    payload = {
        "summary": taste.summary,
        "genres": taste.genres[:8],
        "mood_tags": taste.mood_tags[:6],
        "era_preference": taste.era_preference,
        "energy_range": taste.energy_range,
        "core_taste": taste.core_taste,
        "recent_shift": taste.recent_shift,
        "curation_hints": taste.curation_hints[:6],
        "avoid": taste.avoid[:6],
        "taste_lanes": [
            {
                "label": lane.label,
                "description": lane.description,
                "artists": lane.artists[:5],
            }
            for lane in taste.taste_lanes[:4]
        ],
    }
    return json.dumps(payload, separators=(",", ":"))
