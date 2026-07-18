"""Discovery-specific candidate selection that avoids the user's existing library."""

from __future__ import annotations

import logging
from typing import Any

import spotipy
from spotipy.exceptions import SpotifyException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import User
from app.playlists.cache import load_playlist_list_cache, repair_playlist_list_cache
from app.playlists.service import fetch_playlist_tracks_lite
from app.spotify_candidates import _map_candidate_tracks, _track_to_candidate
from app.spotify_client import paginate
from app.taste.models import TasteProfile

logger = logging.getLogger(__name__)

_MAX_SAVED_TRACKS = 500
_MAX_PLAYLISTS_SCANNED = 10
_MAX_TRACKS_PER_PLAYLIST = 150


def collect_known_track_ids(sp: spotipy.Spotify, db: Session | None = None) -> set[str]:
    """Track IDs the user already listens to, saves, or has in owned playlists."""
    known: set[str] = set()

    for time_range in ("short_term", "medium_term", "long_term"):
        try:
            response = sp.current_user_top_tracks(limit=50, time_range=time_range)
            for track in response.get("items", []):
                if track.get("id"):
                    known.add(str(track["id"]))
        except SpotifyException as exc:
            logger.debug("top tracks lookup failed (%s): %s", time_range, exc)

    try:
        recent = sp.current_user_recently_played(limit=50)
        for item in recent.get("items", []):
            track = item.get("track") or {}
            if track.get("id"):
                known.add(str(track["id"]))
    except SpotifyException as exc:
        logger.debug("recently played lookup failed: %s", exc)

    try:
        saved = paginate(sp, "current_user_saved_tracks", limit=50)
        for item in saved[:_MAX_SAVED_TRACKS]:
            track = item.get("track") or {}
            if track.get("id"):
                known.add(str(track["id"]))
    except SpotifyException as exc:
        logger.debug("saved tracks lookup failed: %s", exc)

    if db is None:
        return known

    user = db.scalars(
        select(User).order_by(User.connected_at.desc(), User.id.desc())
    ).first()
    spotify_user_id = user.spotify_id if user and user.spotify_id else None
    playlists = repair_playlist_list_cache(
        db,
        current_user_id=spotify_user_id,
        current_user_display_name=user.display_name if user else None,
    )
    if playlists is None:
        playlists = load_playlist_list_cache(db) or []

    owned = [
        playlist
        for playlist in playlists
        if playlist.can_edit and playlist.track_count > 0
    ]
    owned.sort(key=lambda playlist: playlist.track_count, reverse=True)

    for playlist in owned[:_MAX_PLAYLISTS_SCANNED]:
        try:
            tracks = fetch_playlist_tracks_lite(
                sp,
                playlist_id=playlist.id,
                max_tracks=_MAX_TRACKS_PER_PLAYLIST,
            )
            for track in tracks:
                known.add(track.id)
        except SpotifyException as exc:
            logger.debug(
                "playlist track lookup failed for %s: %s",
                playlist.id,
                exc,
            )

    return known


def _append_unique_candidates(
    candidates: list[dict[str, Any]],
    batch: list[dict[str, Any]],
    *,
    seen: set[str],
    exclude: set[str],
) -> None:
    for candidate in batch:
        track_id = str(candidate.get("id", ""))
        if not track_id or track_id in seen or track_id in exclude:
            continue
        seen.add(track_id)
        candidates.append(candidate)


def _recommendation_batch(
    sp: spotipy.Spotify,
    *,
    limit: int,
    seed_tracks: list[str] | None = None,
    seed_artists: list[str] | None = None,
    seed_genres: list[str] | None = None,
) -> list[dict[str, Any]]:
    seeds: dict[str, Any] = {}
    if seed_tracks:
        seeds["seed_tracks"] = seed_tracks[:2]
    if seed_artists:
        seeds["seed_artists"] = seed_artists[:2]
    if seed_genres:
        seeds["seed_genres"] = seed_genres[:2]
    if not seeds:
        return []
    try:
        recs = sp.recommendations(limit=limit, **seeds)
    except SpotifyException as exc:
        logger.debug("recommendations batch failed: %s", exc)
        return []
    return _map_candidate_tracks(recs.get("tracks", []))


def _related_artist_candidates(
    sp: spotipy.Spotify,
    taste_profile: TasteProfile,
    *,
    exclude: set[str],
    seen: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    """Pull tracks from artists adjacent to taste but not in the user's top rotation."""
    candidates: list[dict[str, Any]] = []
    top_artists = set(taste_profile.top_artist_ids)

    for artist_id in taste_profile.top_artist_ids[:5]:
        if len(candidates) >= limit:
            break
        try:
            related = sp.artist_related_artists(artist_id)
        except SpotifyException as exc:
            logger.debug("related artists failed for %s: %s", artist_id, exc)
            continue

        for related_artist in related.get("artists", [])[:6]:
            related_id = related_artist.get("id")
            if not related_id or related_id in top_artists:
                continue
            try:
                top_tracks = sp.artist_top_tracks(related_id, country="US")
            except SpotifyException:
                continue
            for track in top_tracks.get("tracks", [])[:2]:
                track_id = track.get("id")
                if not track_id or track_id in exclude or track_id in seen:
                    continue
                seen.add(str(track_id))
                candidates.append(_track_to_candidate(track))
                if len(candidates) >= limit:
                    return candidates

    return candidates


def _genre_search_candidates(
    sp: spotipy.Spotify,
    taste_profile: TasteProfile,
    *,
    exclude: set[str],
    seen: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for genre in taste_profile.seed_genres[:4]:
        if len(candidates) >= limit:
            break
        try:
            result = sp.search(q=f"genre:{genre}", type="track", limit=20)
        except SpotifyException:
            continue
        for track in result.get("tracks", {}).get("items", []):
            track_id = track.get("id")
            if not track_id or track_id in exclude or track_id in seen:
                continue
            seen.add(str(track_id))
            candidates.append(_track_to_candidate(track))
            if len(candidates) >= limit:
                return candidates
    return candidates


def get_discovery_candidates(
    sp: spotipy.Spotify,
    taste_profile: TasteProfile,
    *,
    db: Session | None = None,
    limit: int = 60,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Return fresh candidate tracks excluding the user's existing library."""
    known = collect_known_track_ids(sp, db)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    recommendation_batches = [
        _recommendation_batch(
            sp,
            limit=100,
            seed_genres=taste_profile.seed_genres[:2] or None,
            seed_artists=taste_profile.top_artist_ids[:2] or None,
        ),
        _recommendation_batch(
            sp,
            limit=100,
            seed_genres=taste_profile.seed_genres[:2] or None,
        ),
        _recommendation_batch(
            sp,
            limit=100,
            seed_artists=taste_profile.top_artist_ids[:3] or None,
            seed_genres=taste_profile.seed_genres[:1] or None,
        ),
    ]
    for batch in recommendation_batches:
        _append_unique_candidates(candidates, batch, seen=seen, exclude=known)

    if len(candidates) < limit:
        _append_unique_candidates(
            candidates,
            _related_artist_candidates(
                sp,
                taste_profile,
                exclude=known,
                seen=seen,
                limit=limit * 2,
            ),
            seen=seen,
            exclude=known,
        )

    if len(candidates) < limit // 2:
        _append_unique_candidates(
            candidates,
            _genre_search_candidates(
                sp,
                taste_profile,
                exclude=known,
                seen=seen,
                limit=limit,
            ),
            seen=seen,
            exclude=known,
        )

    logger.info(
        "Discovery candidates: %d fresh tracks (excluded %d known library tracks)",
        len(candidates),
        len(known),
    )
    return candidates[: max(limit, 60)], known


def select_fresh_track_uris(
    candidates: list[dict[str, Any]],
    selected_ids: set[str],
    *,
    known: set[str],
    target_count: int = 20,
) -> list[str]:
    """Pick URIs from AI selection, backfilling only with tracks outside the library."""
    uris: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        track_id = str(candidate.get("id", ""))
        if track_id not in selected_ids or track_id in known or track_id in seen:
            continue
        uri = candidate.get("uri")
        if not uri:
            continue
        seen.add(track_id)
        uris.append(str(uri))

    if len(uris) >= target_count:
        return uris[:target_count]

    for candidate in candidates:
        track_id = str(candidate.get("id", ""))
        if track_id in known or track_id in seen:
            continue
        uri = candidate.get("uri")
        if not uri:
            continue
        seen.add(track_id)
        uris.append(str(uri))
        if len(uris) >= target_count:
            break

    return uris
