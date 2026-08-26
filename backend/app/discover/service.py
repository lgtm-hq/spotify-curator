"""Auto-discovery playlist generation."""

from __future__ import annotations

import json
import logging
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
from app.db import DiscoverRunRecord, dumps_json, loads_json, utcnow
from app.discover_candidates import (
    get_discovery_candidates,
    select_fresh_track_uris,
)
from app.taste.engine import build_taste_profile
from app.taste.models import TasteProfile
from app.track_metadata import enrich_track_uris

logger = logging.getLogger(__name__)


def _load_discover_config() -> dict[str, Any]:
    try:
        with DEFAULT_CONFIG_FILE.open() as f:
            data = yaml.safe_load(f) or {}
        return cast(dict[str, Any], data.get("discover", {}))
    except FileNotFoundError:
        return {}


def _normalize_rationale(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "summary": str(raw.get("summary") or "").strip(),
        "core_genres": [
            str(item).strip()
            for item in raw.get("core_genres", [])
            if str(item).strip()
        ],
        "spotlight_artists": [
            str(item).strip()
            for item in raw.get("spotlight_artists", [])
            if str(item).strip()
        ],
        "discovery_picks": [
            str(item).strip()
            for item in raw.get("discovery_picks", [])
            if str(item).strip()
        ],
        "energy_notes": str(raw.get("energy_notes") or "").strip(),
        "flow_strategy": str(raw.get("flow_strategy") or "").strip(),
        "excluded": [
            str(item).strip() for item in raw.get("excluded", []) if str(item).strip()
        ],
    }


def _run_payload_from_record(record: DiscoverRunRecord) -> dict[str, Any]:
    payload = loads_json(record.tracks_json)
    if not isinstance(payload, dict):
        payload = {}

    tracks = payload.get("tracks", [])
    uris = payload.get("uris", [])
    if not isinstance(tracks, list):
        tracks = []
    if not isinstance(uris, list):
        uris = []

    rationale = _normalize_rationale(payload.get("rationale"))
    reasoning = str(payload.get("reasoning") or "").strip()
    if not rationale.get("summary") and reasoning:
        rationale["summary"] = reasoning

    status = record.status or "pending"
    if status == "saved" and not record.playlist_id:
        status = "pending"

    return {
        "run_id": record.id,
        "status": status,
        "playlist_id": record.playlist_id,
        "name": record.playlist_name,
        "description": str(payload.get("description") or ""),
        "track_count": len(tracks) if tracks else len(uris),
        "track_uris": [str(uri) for uri in uris],
        "tracks": tracks,
        "reasoning": reasoning,
        "rationale": rationale,
        "created_at": record.created_at.isoformat(),
    }


def generate_discovery_proposal(
    sp: spotipy.Spotify,
    *,
    db: Session,
    taste_profile: TasteProfile | None = None,
) -> dict[str, Any]:
    """Generate a discovery playlist proposal without creating it on Spotify."""
    if taste_profile is None:
        taste_profile = build_taste_profile(sp, db=db)

    candidates, known_tracks = get_discovery_candidates(
        sp,
        taste_profile,
        db=db,
        limit=60,
    )

    discover_cfg = _load_discover_config()
    prefix = discover_cfg.get("playlist_name_prefix", "Discover Weekly")
    week = datetime.now().strftime("%Y-%m-%d")

    if load_ai_config().enabled and candidates:
        ai_config = load_ai_config()
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
        selected_ids = {
            str(track_id) for track_id in parsed.get("selected_track_ids", [])
        }
        uris = select_fresh_track_uris(
            candidates,
            selected_ids,
            known=known_tracks,
            target_count=20,
        )
        if not uris:
            uris = select_fresh_track_uris(
                candidates,
                set(),
                known=known_tracks,
                target_count=20,
            )
        name = parsed.get("name", f"{prefix} — {week}")
        description = parsed.get(
            "description",
            "Fresh picks outside your existing playlists",
        )
        reasoning = str(parsed.get("reasoning") or "").strip()
        rationale = _normalize_rationale(parsed.get("rationale"))
        if not rationale.get("summary") and reasoning:
            rationale["summary"] = reasoning
    else:
        uris = select_fresh_track_uris(
            candidates, set(), known=known_tracks, target_count=20
        )
        name = f"{prefix} — {week}"
        description = "Fresh picks outside your existing playlists"
        reasoning = "Selected tracks not already in your library."
        spotlight_artists = []
        for lane in taste_profile.taste_lanes[:2]:
            spotlight_artists.extend(lane.artists[:3])
        rationale = {
            "summary": reasoning,
            "core_genres": taste_profile.genres[:4],
            "spotlight_artists": spotlight_artists[:6],
            "discovery_picks": [],
            "energy_notes": taste_profile.energy_range,
            "flow_strategy": "Filtered to tracks not already in your library.",
            "excluded": taste_profile.avoid[:4],
        }

    if not uris:
        msg = "Could not find enough new tracks outside your library. Try again later."
        raise ValueError(msg)

    tracks = enrich_track_uris(sp, uris, candidates=candidates)

    run_id = str(uuid.uuid4())
    record = DiscoverRunRecord(
        id=run_id,
        playlist_id=None,
        playlist_name=name,
        tracks_json=dumps_json(
            {
                "uris": uris,
                "tracks": tracks,
                "description": description,
                "reasoning": reasoning,
                "rationale": rationale,
            },
        ),
        status="pending",
        created_at=utcnow(),
    )
    db.add(record)
    db.commit()

    return _run_payload_from_record(record)


def save_discovery_run_to_spotify(
    sp: spotipy.Spotify,
    *,
    db: Session,
    run_id: str,
    track_uris: list[str] | None = None,
) -> dict[str, Any]:
    """Create the Spotify playlist for an approved discovery run."""
    record = db.get(DiscoverRunRecord, run_id)
    if record is None:
        msg = "Discovery run not found"
        raise ValueError(msg)

    if record.status == "saved" and record.playlist_id:
        return _run_payload_from_record(record)

    payload = loads_json(record.tracks_json)
    if not isinstance(payload, dict):
        msg = "Invalid discovery run data"
        raise ValueError(msg)

    uris = track_uris or payload.get("uris", [])
    if not isinstance(uris, list) or not uris:
        msg = "No tracks to save"
        raise ValueError(msg)

    description = str(payload.get("description") or "Auto-generated discovery playlist")
    playlist = sp.current_user_playlist_create(
        record.playlist_name,
        public=False,
        description=description,
    )
    for index in range(0, len(uris), 100):
        sp.playlist_add_items(playlist["id"], uris[index : index + 100])

    payload["uris"] = uris
    if track_uris:
        candidates = payload.get("tracks", [])
        if isinstance(candidates, list):
            kept_ids = {
                uri.removeprefix("spotify:track:")
                for uri in uris
                if isinstance(uri, str) and uri.startswith("spotify:track:")
            }
            payload["tracks"] = [
                track
                for track in candidates
                if isinstance(track, dict) and track.get("id") in kept_ids
            ]

    record.playlist_id = playlist["id"]
    record.status = "saved"
    record.tracks_json = dumps_json(payload)
    db.commit()

    result = _run_payload_from_record(record)
    result["spotify_url"] = playlist.get("external_urls", {}).get("spotify")
    return result


def generate_discovery_playlist(
    sp: spotipy.Spotify,
    *,
    db: Session,
    taste_profile: TasteProfile | None = None,
) -> dict[str, Any]:
    """Generate and immediately save a discovery playlist (scheduled jobs)."""
    proposal = generate_discovery_proposal(sp, db=db, taste_profile=taste_profile)
    return save_discovery_run_to_spotify(
        sp,
        db=db,
        run_id=str(proposal["run_id"]),
    )


def _resolve_track_uris(tracks: list[Any], uris: list[Any]) -> list[str]:
    """Build Spotify URIs from stored payload, including legacy rows."""
    resolved = [str(uri) for uri in uris if uri]
    if resolved:
        return resolved
    for track in tracks:
        if not isinstance(track, dict):
            continue
        uri = track.get("uri")
        if uri:
            resolved.append(str(uri))
            continue
        track_id = track.get("id")
        if track_id:
            resolved.append(f"spotify:track:{track_id}")
    return resolved


def _tracks_need_enrichment(tracks: list[Any]) -> bool:
    """True when stored track rows are missing usable display metadata."""
    if not tracks:
        return True
    for track in tracks:
        if not isinstance(track, dict) or not track.get("id"):
            return True
        name = str(track.get("name") or "")
        artists = track.get("artists") or []
        if name.startswith("Track ") or not track.get("duration_ms"):
            return True
        if artists in ([], ["Unknown artist"], ["Unknown"]):
            return True
    return False


def _discover_tracks_from_summaries(tracks: list[Any]) -> list[dict[str, Any]]:
    """Convert playlist track summaries into discover track payloads."""
    from app.playlists.models import TrackSummary

    entries: list[dict[str, Any]] = []
    for item in tracks:
        if isinstance(item, TrackSummary):
            entries.append(
                {
                    "id": item.id,
                    "uri": item.uri,
                    "name": item.name,
                    "artists": [artist.name for artist in item.artists],
                    "album": item.album,
                    "duration_ms": item.duration_ms,
                    "image_url": item.album_image_url,
                    "preview_url": None,
                    "explicit": False,
                },
            )
            continue
        if not isinstance(item, dict):
            continue
        artists = item.get("artists") or []
        artist_names = [
            str(artist.get("name", artist)) if isinstance(artist, dict) else str(artist)
            for artist in artists
        ]
        entries.append(
            {
                "id": str(item.get("id", "")),
                "uri": str(item.get("uri") or ""),
                "name": str(item.get("name") or "Unknown"),
                "artists": artist_names,
                "album": item.get("album"),
                "duration_ms": int(item.get("duration_ms") or 0),
                "image_url": item.get("album_image_url") or item.get("image_url"),
                "preview_url": item.get("preview_url"),
                "explicit": bool(item.get("explicit")),
            },
        )
    return entries


def _persist_run_tracks(
    db: Session,
    record: DiscoverRunRecord,
    *,
    tracks: list[dict[str, Any]],
    uris: list[str],
) -> None:
    """Cache enriched track metadata on the discover run."""
    payload = loads_json(record.tracks_json)
    if not isinstance(payload, dict):
        payload = {}
    payload["tracks"] = tracks
    payload["uris"] = uris
    record.tracks_json = dumps_json(payload)
    db.commit()


def get_discovery_run(
    db: Session,
    *,
    run_id: str,
    sp: spotipy.Spotify | None = None,
) -> dict[str, Any]:
    """Return a discovery run with full proposal payload."""
    record = db.get(DiscoverRunRecord, run_id)
    if record is None:
        msg = "Discovery run not found"
        raise ValueError(msg)
    result = _run_payload_from_record(record)
    track_uris = _resolve_track_uris(result["tracks"], result["track_uris"])
    result["track_uris"] = track_uris

    if sp is None:
        return result

    enriched_tracks: list[dict[str, Any]] | None = None
    enriched_uris = track_uris

    if record.playlist_id:
        from app.playlists.service import fetch_playlist_tracks_lite

        try:
            playlist_tracks = fetch_playlist_tracks_lite(
                sp,
                playlist_id=record.playlist_id,
                max_tracks=max(len(track_uris), result["track_count"], 100),
            )
            if playlist_tracks:
                enriched_tracks = _discover_tracks_from_summaries(playlist_tracks)
                enriched_uris = [
                    track["uri"] for track in enriched_tracks if track.get("uri")
                ]
        except Exception:
            logger.exception(
                "Failed to load Spotify playlist tracks for discover run %s",
                run_id,
            )

    if (
        enriched_tracks is None
        and track_uris
        and _tracks_need_enrichment(result["tracks"])
    ):
        enriched_tracks = enrich_track_uris(sp, track_uris)
        enriched_uris = track_uris

    if enriched_tracks and not _tracks_need_enrichment(enriched_tracks):
        result["tracks"] = enriched_tracks
        result["track_uris"] = enriched_uris
        result["track_count"] = len(enriched_tracks)
        if _tracks_need_enrichment(_run_payload_from_record(record)["tracks"]):
            _persist_run_tracks(
                db,
                record,
                tracks=enriched_tracks,
                uris=enriched_uris,
            )

    return result


def delete_discovery_run(db: Session, *, run_id: str) -> None:
    """Remove a discovery run from history."""
    record = db.get(DiscoverRunRecord, run_id)
    if record is None:
        msg = "Discovery run not found"
        raise ValueError(msg)
    db.delete(record)
    db.commit()


def remove_discovery_run(
    db: Session,
    *,
    run_id: str,
    sp: spotipy.Spotify | None = None,
    remove_history: bool = True,
    delete_playlist: bool = False,
) -> dict[str, str]:
    """Remove a discovery run from history and/or delete its Spotify playlist."""
    if not remove_history and not delete_playlist:
        msg = "Choose at least one remove action."
        raise ValueError(msg)

    record = db.get(DiscoverRunRecord, run_id)
    if record is None:
        msg = "Discovery run not found"
        raise ValueError(msg)

    playlist_id = record.playlist_id

    if delete_playlist:
        if not playlist_id:
            msg = "This run has no Spotify playlist to delete."
            raise ValueError(msg)
        if sp is None:
            msg = "Spotify client required to delete playlist."
            raise ValueError(msg)
        from app.playlists.cache import remove_playlist_from_spotify_cache
        from app.playlists.service import unfollow_playlist

        unfollow_playlist(sp, playlist_id=playlist_id)
        remove_playlist_from_spotify_cache(db, playlist_id=playlist_id)

    if remove_history:
        db.delete(record)
    elif delete_playlist:
        record.playlist_id = None
        record.status = "dismissed"

    db.commit()
    return {"status": "removed"}
