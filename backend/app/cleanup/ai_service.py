"""AI-powered cleanup suggestions across the playlist library."""

from __future__ import annotations

from app.cleanup.playlist_scan import (
    PlaylistScanStats,
    scan_playlist_full,
    select_playlists_to_scan,
)
from app.cleanup.suggest_jobs import (
    create_suggest_job,
    get_suggest_job,
    run_suggest_job,
)

__all__ = [
    "PlaylistScanStats",
    "create_suggest_job",
    "get_suggest_job",
    "run_suggest_job",
    "scan_playlist_full",
    "select_playlists_to_scan",
]
