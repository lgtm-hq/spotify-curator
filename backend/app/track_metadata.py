"""Enrich Spotify track URIs with display metadata."""

from __future__ import annotations

import logging
from typing import Any

import spotipy
from spotipy.exceptions import SpotifyException

logger = logging.getLogger(__name__)


def _track_id_from_uri(uri: str) -> str | None:
    if uri.startswith("spotify:track:"):
        return uri.removeprefix("spotify:track:")
    return None


def _format_track(
    *,
    track_id: str,
    uri: str,
    name: str,
    artists: list[str],
    album: str | None = None,
    duration_ms: int = 0,
    image_url: str | None = None,
    preview_url: str | None = None,
    explicit: bool = False,
) -> dict[str, Any]:
    return {
        "id": track_id,
        "uri": uri,
        "name": name,
        "artists": artists,
        "album": album,
        "duration_ms": duration_ms,
        "image_url": image_url,
        "preview_url": preview_url,
        "explicit": explicit,
    }


def _spotify_track_to_entry(track: dict[str, Any]) -> dict[str, Any]:
    images = (track.get("album") or {}).get("images") or []
    return _format_track(
        track_id=str(track["id"]),
        uri=str(track.get("uri", f"spotify:track:{track['id']}")),
        name=str(track.get("name", "Unknown")),
        artists=[str(a.get("name", "Unknown")) for a in track.get("artists", [])],
        album=(track.get("album") or {}).get("name"),
        duration_ms=int(track.get("duration_ms") or 0),
        image_url=images[0]["url"] if images else None,
        preview_url=track.get("preview_url"),
        explicit=bool(track.get("explicit")),
    )


def _candidate_maps(
    candidates: list[dict[str, Any]] | None,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_uri: dict[str, dict[str, Any]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates or []:
        uri = candidate.get("uri")
        track_id = candidate.get("id")
        if isinstance(uri, str):
            by_uri[uri] = candidate
        if isinstance(track_id, str):
            by_id[track_id] = candidate
    return by_uri, by_id


def _entry_from_candidate(
    *,
    track_id: str,
    uri: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    return _format_track(
        track_id=track_id,
        uri=uri,
        name=str(candidate.get("name", "Unknown")),
        artists=[str(a) for a in candidate.get("artists", [])],
    )


def _fetch_track_details(
    sp: spotipy.Spotify,
    track_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch track metadata from Spotify when the API allows it."""
    details: dict[str, dict[str, Any]] = {}
    if not track_ids:
        return details

    try:
        for index in range(0, len(track_ids), 50):
            batch = track_ids[index : index + 50]
            response = sp.tracks(batch)
            for track in response.get("tracks", []):
                if track and track.get("id"):
                    details[str(track["id"])] = track
    except SpotifyException as exc:
        logger.warning(
            "Spotify tracks lookup unavailable (%s); using candidate metadata only",
            exc,
        )
    return details


def enrich_track_uris(
    sp: spotipy.Spotify,
    track_uris: list[str],
    *,
    candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Resolve playlist URIs into track entries with metadata."""
    candidate_by_uri, candidate_by_id = _candidate_maps(candidates)

    track_ids = [
        track_id
        for uri in track_uris
        if (track_id := _track_id_from_uri(uri)) is not None
    ]
    details = _fetch_track_details(sp, track_ids)

    entries: list[dict[str, Any]] = []
    for uri in track_uris:
        track_id = _track_id_from_uri(uri)
        if track_id is None:
            continue

        detail = details.get(track_id)
        if detail:
            entries.append(_spotify_track_to_entry(detail))
            continue

        candidate = candidate_by_uri.get(uri) or candidate_by_id.get(track_id)
        if candidate:
            entries.append(
                _entry_from_candidate(track_id=track_id, uri=uri, candidate=candidate),
            )
            continue

        entries.append(
            _format_track(
                track_id=track_id,
                uri=uri,
                name=f"Track {track_id[:8]}…",
                artists=["Unknown artist"],
            ),
        )

    return entries
