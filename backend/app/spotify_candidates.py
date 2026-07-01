"""Spotify track candidate discovery with recommendations fallback."""

from __future__ import annotations

import logging
from typing import Any

import spotipy
from spotipy.exceptions import SpotifyException

from app.taste.models import TasteProfile

logger = logging.getLogger(__name__)


def _track_to_candidate(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": track["id"],
        "uri": track["uri"],
        "name": track.get("name", "Unknown"),
        "artists": [a["name"] for a in track.get("artists", [])],
    }


def _map_candidate_tracks(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_track_to_candidate(track) for track in tracks if track.get("id")]


def _fallback_candidates(
    sp: spotipy.Spotify,
    taste_profile: TasteProfile,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Build candidate tracks when Spotify recommendations is unavailable."""
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []

    def add_tracks(tracks: list[dict[str, Any]]) -> None:
        for track in tracks:
            track_id = track.get("id")
            if not track_id or track_id in seen:
                continue
            seen.add(track_id)
            candidates.append(_track_to_candidate(track))
            if len(candidates) >= limit:
                return

    for artist_id in taste_profile.top_artist_ids[:5]:
        if len(candidates) >= limit:
            break
        try:
            top = sp.artist_top_tracks(artist_id, country="US")
            add_tracks(top.get("tracks", []))
        except SpotifyException as exc:
            logger.debug("artist_top_tracks failed for %s: %s", artist_id, exc)

    for genre in taste_profile.seed_genres[:3]:
        if len(candidates) >= limit:
            break
        try:
            result = sp.search(q=f"genre:{genre}", type="track", limit=20)
            add_tracks(result.get("tracks", {}).get("items", []))
        except SpotifyException as exc:
            logger.debug("genre search failed for %s: %s", genre, exc)

    if len(candidates) < limit:
        try:
            top = sp.current_user_top_tracks(limit=min(limit, 50))
            tracks = [
                item.get("track") or item for item in top.get("items", []) if item
            ]
            add_tracks(tracks)
        except SpotifyException as exc:
            logger.debug("current_user_top_tracks fallback failed: %s", exc)

    logger.info("Using fallback candidates: %d tracks", len(candidates))
    return candidates


def get_recommendation_candidates(
    sp: spotipy.Spotify,
    taste_profile: TasteProfile,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return candidate tracks for playlist curation/discovery."""
    seeds: dict[str, Any] = {}
    if taste_profile.top_track_ids:
        seeds["seed_tracks"] = taste_profile.top_track_ids[:2]
    if taste_profile.top_artist_ids:
        seeds["seed_artists"] = taste_profile.top_artist_ids[:2]
    if taste_profile.seed_genres:
        seeds["seed_genres"] = taste_profile.seed_genres[:1]

    if seeds:
        try:
            recs = sp.recommendations(limit=limit, **seeds)
            candidates = _map_candidate_tracks(recs.get("tracks", []))
            if candidates:
                return candidates
        except SpotifyException as exc:
            logger.warning(
                "Spotify recommendations unavailable (%s), using fallback",
                exc,
            )

    return _fallback_candidates(sp, taste_profile, limit=limit)
