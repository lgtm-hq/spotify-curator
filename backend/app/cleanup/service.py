"""Cleanup analysis and application."""

from __future__ import annotations

import logging
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import spotipy
from rapidfuzz import fuzz
from sklearn.cluster import KMeans
from sqlalchemy.orm import Session

from app.db import CleanupRunRecord, dumps_json, utcnow
from app.playlists.models import TrackSummary
from app.playlists.service import get_playlist
from app.spotify_client import playlist_entry_track


def _normalize_title(name: str) -> str:
    """Normalize track title for fuzzy matching."""
    lowered = name.lower()
    lowered = re.sub(r"\(.*?(remaster|live|mix|version).*?\)", "", lowered)
    lowered = re.sub(r"[^\w\s]", " ", lowered)
    return " ".join(lowered.split())


@dataclass
class CleanupIssue:
    """A single cleanup finding."""

    kind: str
    track_ids: list[str]
    reason: str
    tracks: list[TrackSummary] = field(default_factory=list)


@dataclass
class SplitProposal:
    """Proposed playlist split."""

    name: str
    track_ids: list[str]
    cluster_label: str


@dataclass
class CleanupAnalysis:
    """Full cleanup analysis result."""

    playlist_id: str
    duplicates: list[CleanupIssue]
    unavailable: list[CleanupIssue]
    skip_heavy: list[CleanupIssue]
    clusters: list[SplitProposal]
    total_tracks: int


def find_duplicates(tracks: list[TrackSummary]) -> list[CleanupIssue]:
    """Find duplicate tracks by ID and fuzzy title+artist match."""
    issues: list[CleanupIssue] = []
    by_id: dict[str, list[TrackSummary]] = defaultdict(list)
    for track in tracks:
        by_id[track.id].append(track)

    for track_id, group in by_id.items():
        if len(group) > 1:
            issues.append(
                CleanupIssue(
                    kind="duplicate_id",
                    track_ids=[t.id for t in group[1:]],
                    reason=f"Duplicate track ID {track_id}",
                    tracks=group,
                ),
            )

    seen_keys: dict[str, TrackSummary] = {}
    for track in tracks:
        artist = track.artists[0].name if track.artists else ""
        key = f"{_normalize_title(track.name)}|{artist.lower()}"
        if key in seen_keys:
            existing = seen_keys[key]
            score = fuzz.ratio(
                _normalize_title(track.name),
                _normalize_title(existing.name),
            )
            if score >= 85:
                issues.append(
                    CleanupIssue(
                        kind="duplicate_fuzzy",
                        track_ids=[track.id],
                        reason=f"Similar to '{existing.name}' by {artist}",
                        tracks=[existing, track],
                    ),
                )
        else:
            seen_keys[key] = track
    return issues


def find_unavailable(tracks: list[TrackSummary]) -> list[CleanupIssue]:
    """Find tracks that are not playable."""
    bad = [t for t in tracks if not t.is_playable]
    if not bad:
        return []
    return [
        CleanupIssue(
            kind="unavailable",
            track_ids=[t.id for t in bad],
            reason="Track unavailable in your market",
            tracks=bad,
        ),
    ]


def find_skip_heavy(
    tracks: list[TrackSummary],
    *,
    recently_played: list[dict[str, Any]],
    skip_threshold: float = 0.7,
) -> list[CleanupIssue]:
    """Flag tracks with high skip rates from recently played history."""
    skip_counts: Counter[str] = Counter()
    play_counts: Counter[str] = Counter()
    for item in recently_played:
        track = item.get("track") or {}
        track_id = track.get("id")
        if not track_id:
            continue
        play_counts[track_id] += 1
        if item.get("skipped"):
            skip_counts[track_id] += 1

    heavy: list[TrackSummary] = []
    track_map = {t.id: t for t in tracks}
    for track_id, plays in play_counts.items():
        if track_id not in track_map:
            continue
        rate = skip_counts[track_id] / plays
        if rate >= skip_threshold and plays >= 2:
            heavy.append(track_map[track_id])

    if not heavy:
        return []
    return [
        CleanupIssue(
            kind="skip_heavy",
            track_ids=[t.id for t in heavy],
            reason=f"Skipped >= {int(skip_threshold * 100)}% of recent plays",
            tracks=heavy,
        ),
    ]


def cluster_by_audio_features(
    tracks: list[TrackSummary],
    *,
    features_by_id: dict[str, dict[str, Any]],
    n_clusters: int = 4,
) -> list[SplitProposal]:
    """Cluster tracks by audio features for split proposals."""
    vectors: list[list[float]] = []
    ids: list[str] = []
    for track in tracks:
        feat = features_by_id.get(track.id)
        if not feat:
            continue
        vectors.append(
            [
                feat.get("energy", 0.5),
                feat.get("valence", 0.5),
                feat.get("danceability", 0.5),
                min(feat.get("tempo", 120) / 200.0, 1.0),
            ],
        )
        ids.append(track.id)

    if len(vectors) < n_clusters:
        return []

    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(
        np.array(vectors),
    )
    clusters: dict[int, list[str]] = defaultdict(list)
    for track_id, label in zip(ids, labels, strict=True):
        clusters[int(label)].append(track_id)

    labels_map = {
        0: "Chill",
        1: "Energetic",
        2: "Melancholy",
        3: "Upbeat",
    }
    proposals: list[SplitProposal] = []
    for idx, track_ids in clusters.items():
        proposals.append(
            SplitProposal(
                name=f"Cluster {idx + 1}",
                track_ids=track_ids,
                cluster_label=labels_map.get(idx % 4, f"Mood {idx + 1}"),
            ),
        )
    return proposals


async def analyze_playlist(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
    db: Session,
) -> CleanupAnalysis:
    """Run full cleanup analysis on a playlist."""
    detail = get_playlist(sp, playlist_id=playlist_id)
    duplicates = find_duplicates(detail.tracks)
    unavailable = find_unavailable(detail.tracks)

    recent = sp.current_user_recently_played(limit=50)
    skip_heavy = find_skip_heavy(
        detail.tracks,
        recently_played=recent.get("items", []),
    )

    features_by_id: dict[str, dict[str, Any]] = {}
    track_ids = [t.id for t in detail.tracks if t.id]
    for i in range(0, len(track_ids), 100):
        batch = track_ids[i : i + 100]
        try:
            feats = sp.audio_features(batch)
            for feat in feats or []:
                if feat and feat.get("id"):
                    features_by_id[feat["id"]] = feat
        except Exception as exc:
            logging.debug("audio_features unavailable for batch: %s", exc)

    clusters = cluster_by_audio_features(detail.tracks, features_by_id=features_by_id)

    return CleanupAnalysis(
        playlist_id=playlist_id,
        duplicates=duplicates,
        unavailable=unavailable,
        skip_heavy=skip_heavy,
        clusters=clusters,
        total_tracks=len(detail.tracks),
    )


def apply_removals(
    sp: spotipy.Spotify,
    *,
    playlist_id: str,
    track_ids: list[str],
    db: Session,
) -> dict[str, int]:
    """Remove tracks from a playlist."""
    if not track_ids:
        return {"removed": 0}
    # Fetch snapshot for removals
    items = sp.playlist_items(
        playlist_id,
        limit=100,
        offset=0,
        additional_types=["track"],
    )
    all_items = items.get("items", [])
    offset = 100
    while items.get("next"):
        items = sp.playlist_items(
            playlist_id,
            limit=100,
            offset=offset,
            additional_types=["track"],
        )
        all_items.extend(items.get("items", []))
        offset += 100

    remove_ids = set(track_ids)
    positions = [
        track["uri"]
        for entry in all_items
        if (track := playlist_entry_track(entry)) and track.get("id") in remove_ids
    ]
    if positions:
        sp.playlist_remove_all_occurrences_of_items(playlist_id, positions)

    record = CleanupRunRecord(
        id=str(uuid.uuid4()),
        playlist_id=playlist_id,
        action="remove_tracks",
        details_json=dumps_json({"track_ids": track_ids, "count": len(positions)}),
        created_at=utcnow(),
    )
    db.add(record)
    db.commit()
    return {"removed": len(positions)}


def apply_split(
    sp: spotipy.Spotify,
    *,
    source_playlist_id: str,
    proposals: list[SplitProposal],
    user_id: str,
    db: Session,
) -> list[dict[str, Any]]:
    """Create new playlists from split proposals."""
    created: list[dict[str, Any]] = []
    for proposal in proposals:
        playlist = sp.user_playlist_create(
            user_id,
            f"{proposal.cluster_label} Mix",
            public=False,
            description=f"Split from playlist {source_playlist_id}",
        )
        uris = [f"spotify:track:{tid}" for tid in proposal.track_ids]
        for i in range(0, len(uris), 100):
            sp.playlist_add_items(playlist["id"], uris[i : i + 100])
        created.append(
            {"id": playlist["id"], "name": playlist["name"], "tracks": len(uris)},
        )

    record = CleanupRunRecord(
        id=str(uuid.uuid4()),
        playlist_id=source_playlist_id,
        action="split_playlist",
        details_json=dumps_json({"created": created}),
        created_at=utcnow(),
    )
    db.add(record)
    db.commit()
    return created
