import type { CleanupSuggestOptions } from "../../api/client";

export const DEFAULT_ADVISOR_OPTIONS: CleanupSuggestOptions = {
  scope: "all_owned",
  playlist_ids: [],
  exclude_playlist_ids: [],
  user_prompt: null,
  use_scan_cache: true,
  force_rescan: false,
  min_track_count: 1,
  focus_areas: ["duplicates", "unavailable", "bloated"],
  conservative_scan: false,
  sort_by: "track_count_desc",
  stale_after_days: null,
  min_duplicates: 0,
  min_unavailable: 0,
  min_bloated_tracks: 150,
  include_taste_profile: true,
  custom_taste_summary: null,
  quick_start_id: "full-audit",
};
