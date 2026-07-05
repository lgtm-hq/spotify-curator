"""Re-exports for cleanup AI scan helpers."""

from app.cleanup.advisor_presets import list_presets, save_preset
from app.cleanup.playlist_resolution import estimate_scan, resolve_playlists_to_scan
from app.cleanup.playlist_scan import (
    PlaylistScanStats,
    filter_scans_by_focus,
    filter_scans_by_thresholds,
    scan_playlist_full,
    scan_playlists_parallel,
)
from app.cleanup.suggest_jobs import (
    create_suggest_job,
    get_suggest_job,
    run_suggest_job,
)
from app.cleanup.suggest_options import CleanupSuggestOptions

__all__ = [
    "CleanupSuggestOptions",
    "PlaylistScanStats",
    "create_suggest_job",
    "estimate_scan",
    "filter_scans_by_focus",
    "filter_scans_by_thresholds",
    "get_suggest_job",
    "list_presets",
    "resolve_playlists_to_scan",
    "run_suggest_job",
    "save_preset",
    "scan_playlist_full",
    "scan_playlists_parallel",
]
