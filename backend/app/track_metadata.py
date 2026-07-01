"""Enrich Spotify track URIs with display metadata."""

from __future__ import annotations

from typing import Any

import spotipy


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


def enrich_track_uris(
    sp: spotipy.Spotify,
    track_uris: list[str],
    *,
    candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Resolve playlist URIs into track entries with metadata."""
    candidate_by_uri = {
        str(c["uri"]): c for c in (candidates or []) if isinstance(c.get("uri"), str)
    }

    track_ids = [
        track_id
        for uri in track_uris
        if (track_id := _track_id_from_uri(uri)) is not None
    ]

    details: dict[str, dict[str, Any]] = {}
    for index in range(0, len(track_ids), 50):
        batch = track_ids[index : index + 50]
        response = sp.tracks(batch)
        for track in response.get("tracks", []):
            if track and track.get("id"):
                details[str(track["id"])] = track

    entries: list[dict[str, Any]] = []
    for uri in track_uris:
        track_id = _track_id_from_uri(uri)
        if track_id is None:
            continue

        detail = details.get(track_id)
        if detail:
            entries.append(_spotify_track_to_entry(detail))
            continue

        candidate = candidate_by_uri.get(uri)
        if candidate:
            entries.append(
                _format_track(
                    track_id=track_id,
                    uri=uri,
                    name=str(candidate.get("name", "Unknown")),
                    artists=[str(a) for a in candidate.get("artists", [])],
                ),
            )
            continue

        entries.append(
            _format_track(
                track_id=track_id,
                uri=uri,
                name="Unknown track",
                artists=["Unknown"],
            ),
        )

    return entries
