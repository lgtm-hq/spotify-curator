import { notifySpotifyUsageInvalidate } from "../utils/spotifyUsageEvents";

const API_BASE = "";

export class RequestCancelledError extends Error {
  constructor() {
    super("Cancelled");
    this.name = "RequestCancelledError";
  }
}

export function isRequestCancelled(error: unknown): boolean {
  return error instanceof RequestCancelledError;
}

type ApiRequestOptions = RequestInit & {
  signal?: AbortSignal;
  timeoutMs?: number;
};

async function parseErrorDetail(response: Response, fallback: string): Promise<string> {
  const text = await response.text();
  try {
    const data = JSON.parse(text) as { detail?: unknown };
    if (typeof data.detail === "string") {
      return data.detail;
    }
  } catch {
    // Response was not JSON — use raw text below.
  }
  return text.trim() || fallback;
}

async function request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { signal: externalSignal, timeoutMs = 20_000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  const abortFromExternal = () => controller.abort();
  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort();
    } else {
      externalSignal.addEventListener("abort", abortFromExternal);
    }
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      signal: controller.signal,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(fetchOptions.headers ?? {}),
      },
    });
    if (!response.ok) {
      if (response.status === 429) {
        notifySpotifyUsageInvalidate();
      }
      throw new Error(await parseErrorDetail(response, `Request failed: ${response.status}`));
    }
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      if (externalSignal?.aborted) {
        throw new RequestCancelledError();
      }
      throw new Error("Request timed out. The server may be busy — try again in a moment.");
    }
    throw error;
  } finally {
    if (externalSignal) {
      externalSignal.removeEventListener("abort", abortFromExternal);
    }
    window.clearTimeout(timeout);
  }
}

export interface PlaylistSummary {
  id: string;
  name: string;
  description: string | null;
  owner: string;
  owner_id: string;
  track_count: number;
  image_url: string | null;
  public: boolean;
  can_edit: boolean;
  library_order?: number;
}

export interface TrackSummary {
  id: string;
  name: string;
  artists: { id: string | null; name: string }[];
  uri: string;
  is_playable: boolean;
  album: string | null;
  album_image_url: string | null;
  duration_ms: number;
}

export interface PlaylistDetail extends PlaylistSummary {
  tracks: TrackSummary[];
}

export interface SpotifyUsageStatus {
  state: "ok" | "warning" | "limited";
  requests_in_window: number;
  window_seconds: number;
  estimated_limit: number;
  usage_percent: number;
  rate_limited_until: string | null;
  seconds_until_reset: number | null;
  last_fetched_at: string | null;
}

export interface CuratedPlaylistSource {
  source: "discover" | "curate";
  label: string;
  created_at?: string | null;
}

export interface PlaylistsResponse {
  playlists: PlaylistSummary[];
  last_fetched_at: string | null;
  from_cache: boolean;
  cache_message: string | null;
  spotify_usage: SpotifyUsageStatus | null;
  curated_sources?: Record<string, CuratedPlaylistSource>;
}

export interface PlaylistScanSummary {
  playlist_id: string;
  playlist_name: string;
  track_count: number;
  tracks_scanned: number;
  duplicate_tracks: number;
  unavailable_tracks: number;
  owned: boolean;
  full_scan: boolean;
  from_cache?: boolean;
}

export interface DiscoverRationale {
  summary: string;
  core_genres: string[];
  spotlight_artists: string[];
  discovery_picks: string[];
  energy_notes: string;
  flow_strategy: string;
  excluded: string[];
}

export interface DiscoverTrack {
  id: string;
  uri: string;
  name: string;
  artists: string[];
  album: string | null;
  duration_ms: number;
  image_url: string | null;
  preview_url: string | null;
  explicit: boolean;
}

export interface DiscoverProposal {
  run_id: string;
  status: "pending" | "saved" | "dismissed";
  playlist_id: string | null;
  name: string;
  description: string;
  track_count: number;
  track_uris: string[];
  tracks: DiscoverTrack[];
  reasoning: string;
  rationale: DiscoverRationale;
  created_at?: string;
  spotify_url?: string | null;
}

export interface DiscoverHistoryItem {
  run_id: string;
  playlist_id: string | null;
  name: string;
  status: "pending" | "saved" | "dismissed";
  track_count: number;
  created_at: string;
  legacy_auto_saved?: boolean;
}

export interface TasteLane {
  label: string;
  description: string;
  artists: string[];
}

export interface TasteProfile {
  summary: string;
  genres: string[];
  mood_tags: string[];
  era_preference: string;
  energy_range: string;
  taste_lanes?: TasteLane[];
  core_taste?: string;
  recent_shift?: string;
  curation_hints?: string[];
  avoid?: string[];
  confidence?: "high" | "medium" | "low" | string;
  audio_features_summary?: string;
}

export interface MeResponse {
  connected: boolean;
  user_id: string;
  display_name: string | null;
  email: string | null;
  image_url: string | null;
  connected_at: string | null;
  has_taste_profile: boolean;
  taste_updated_at: string | null;
}

export interface AccountResponse {
  user: {
    spotify_id: string;
    display_name: string;
    email: string | null;
    image_url: string | null;
    product: string | null;
    connected_at: string;
  } | null;
  has_taste_profile: boolean;
  taste_updated_at: string | null;
  data_storage: {
    database: string;
    description: string;
    stored_data: { key: string; description: string }[];
  };
}

export interface CleanupIssue {
  kind: string;
  track_ids: string[];
  reason: string;
  tracks?: TrackSummary[];
}

export interface CleanupCluster {
  name: string;
  track_ids: string[];
  cluster_label: string;
}

export interface CleanupAnalysis {
  playlist_id: string;
  total_tracks: number;
  duplicates: CleanupIssue[];
  unavailable: CleanupIssue[];
  skip_heavy: CleanupIssue[];
  clusters: CleanupCluster[];
}

export interface CleanupSuggestion {
  playlist_id: string;
  playlist_name: string;
  priority?: "high" | "medium" | "low";
  kind?: string;
  title: string;
  description: string;
  recommended_action: string;
}

export interface CleanupSuggestOptions {
  scope: "all_owned" | "selected" | "all_in_library";
  playlist_ids: string[];
  exclude_playlist_ids: string[];
  user_prompt: string | null;
  use_scan_cache: boolean;
  force_rescan: boolean;
  min_track_count: number;
  focus_areas: ("duplicates" | "unavailable" | "bloated")[];
  conservative_scan: boolean;
  sort_by:
    | "track_count_desc"
    | "track_count_asc"
    | "name_asc"
    | "name_desc"
    | "stale_first"
    | "recently_scanned";
  stale_after_days: number | null;
  min_duplicates: number;
  min_unavailable: number;
  min_bloated_tracks: number;
  include_taste_profile: boolean;
  custom_taste_summary: string | null;
  quick_start_id: string | null;
}

export interface AdvisorScanEstimate {
  playlist_count: number;
  cached_count: number;
  fresh_scan_count: number;
  estimated_api_calls: number;
  estimated_seconds_min: number;
  estimated_seconds_max: number;
}

export interface AdvisorPreset {
  id: string;
  name: string;
  description: string;
  builtin: boolean;
  kind?: "intent" | "configuration";
  ai_context?: string;
  options?: CleanupSuggestOptions;
  created_at?: string;
  updated_at?: string;
}

export interface AdvisorSchedule {
  enabled: boolean;
  cron: string;
  options: CleanupSuggestOptions;
  notify_email: boolean;
  last_run_at: string | null;
  last_run_status: string | null;
  last_run_summary: string | null;
  last_job_id: string | null;
  updated_at: string | null;
}

export interface AdvisorScheduleRun {
  id: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  summary: string | null;
  error: string | null;
  triggered_by: string;
  result: CleanupAiSuggestResult | null;
}

export interface CleanupAiSuggestResult {
  summary: string;
  scanned_playlists: number;
  total_playlists: number;
  suggestions: CleanupSuggestion[];
}

export interface CleanupSuggestJobProgress {
  phase: string;
  playlist_index: number;
  playlist_total: number;
  playlist_name: string;
  track_total: number;
  tracks_loaded: number;
  playlists_completed: number;
}

export interface CleanupSuggestJob {
  job_id: string;
  status: "scanning" | "ai" | "completed" | "failed" | "cancelled";
  progress: CleanupSuggestJobProgress;
  result: CleanupAiSuggestResult | null;
  error: string | null;
}

export const api = {
  me: () => request<MeResponse>("/auth/me"),
  account: () => request<AccountResponse>("/auth/account"),
  logout: () => request<{ status: string }>("/auth/logout", { method: "POST" }),
  login: () => {
    window.location.href = "/auth/login";
  },
  playlists: () => request<PlaylistsResponse>("/playlists"),
  spotifyUsage: () => request<SpotifyUsageStatus>("/playlists/usage", { timeoutMs: 15_000 }),
  playlistsRefresh: () => request<PlaylistsResponse>("/playlists/refresh", { method: "POST" }),
  playlistScanSummaries: () =>
    request<Record<string, PlaylistScanSummary>>("/playlists/scan-summaries"),
  playlistScanSummariesRefresh: () =>
    request<{ status: string }>("/playlists/scan-summaries/refresh", {
      method: "POST",
    }),
  playlist: (playlistId: string) => request<PlaylistDetail>(`/playlists/${playlistId}`),
  playlistUpdate: (
    playlistId: string,
    payload: { name?: string; description?: string; public?: boolean },
  ) =>
    request<PlaylistSummary>(`/playlists/${playlistId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  playlistDelete: (playlistId: string) =>
    request<{ status: string }>(`/playlists/${playlistId}`, { method: "DELETE" }),
  playlistRemoveTracks: (
    playlistId: string,
    payload: { track_ids?: string[]; track_uris?: string[] },
  ) =>
    request<{ removed: number }>(`/playlists/${playlistId}/tracks/remove`, {
      method: "POST",
      body: JSON.stringify({
        track_ids: payload.track_ids ?? [],
        track_uris: payload.track_uris ?? [],
      }),
    }),
  playlistReorderTracks: (
    playlistId: string,
    payload: { range_start: number; insert_before: number; range_length?: number },
  ) =>
    request<{ status: string }>(`/playlists/${playlistId}/tracks/reorder`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  taste: (refresh = false) => request<TasteProfile>(`/taste?refresh=${refresh}`),
  tasteRefresh: () =>
    request<TasteProfile>("/taste/refresh", {
      method: "POST",
    }),
  cleanupAnalyze: (playlistId: string) =>
    request<CleanupAnalysis>(`/cleanup/analyze/${playlistId}`, {
      method: "POST",
    }),
  cleanupAiSuggestStart: (options: CleanupSuggestOptions) =>
    request<{ job_id: string; status: string; options: CleanupSuggestOptions }>(
      "/cleanup/ai/suggest",
      {
        method: "POST",
        body: JSON.stringify(options),
        timeoutMs: 60_000,
      },
    ),
  cleanupAiSuggestJob: (jobId: string) =>
    request<CleanupSuggestJob>(`/cleanup/ai/suggest/jobs/${jobId}`, {
      timeoutMs: 120_000,
    }),
  cleanupAiSuggestCancel: (jobId: string) =>
    request<CleanupSuggestJob>(`/cleanup/ai/suggest/jobs/${jobId}/cancel`, {
      method: "POST",
      timeoutMs: 30_000,
    }),
  cleanupAiPresets: () => request<{ presets: AdvisorPreset[] }>("/cleanup/ai/presets"),
  cleanupAiPresetSave: (payload: {
    name: string;
    description?: string;
    options: CleanupSuggestOptions;
  }) =>
    request<AdvisorPreset>("/cleanup/ai/presets", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cleanupAiPresetDelete: (presetId: string) =>
    request<{ status: string }>(`/cleanup/ai/presets/${presetId}`, {
      method: "DELETE",
    }),
  cleanupAiSchedule: () => request<AdvisorSchedule>("/cleanup/ai/schedule"),
  cleanupAiScheduleUpdate: (payload: {
    enabled: boolean;
    cron: string;
    options: CleanupSuggestOptions;
    notify_email: boolean;
  }) =>
    request<AdvisorSchedule>("/cleanup/ai/schedule", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  cleanupAiScheduleRuns: () => request<{ runs: AdvisorScheduleRun[] }>("/cleanup/ai/schedule/runs"),
  cleanupAiEstimate: (options: CleanupSuggestOptions) =>
    request<AdvisorScanEstimate>("/cleanup/ai/estimate", {
      method: "POST",
      body: JSON.stringify(options),
    }),
  cleanupRemove: (playlistId: string, trackIds: string[]) =>
    request<{ removed: number }>("/cleanup/apply/remove", {
      method: "POST",
      body: JSON.stringify({ playlist_id: playlistId, track_ids: trackIds }),
    }),
  cleanupSplit: (sourcePlaylistId: string, proposals: unknown[]) =>
    request<{ created: unknown[] }>("/cleanup/apply/split", {
      method: "POST",
      body: JSON.stringify({
        source_playlist_id: sourcePlaylistId,
        proposals,
      }),
    }),
  curateStart: (options: { signal?: AbortSignal } = {}) =>
    request<{
      session_id: string;
      done: boolean;
      question?: string;
      options?: string[];
      playlist_brief?: string;
    }>("/curate/start", { method: "POST", signal: options.signal, timeoutMs: 120_000 }),
  curateAnswer: (sessionId: string, answer: string, options: { signal?: AbortSignal } = {}) =>
    request<{
      session_id: string;
      done: boolean;
      question?: string;
      options?: string[];
      playlist_brief?: string;
    }>("/curate/answer", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, answer }),
      signal: options.signal,
      timeoutMs: 120_000,
    }),
  curateBuild: (sessionId: string, feedback?: string, options: { signal?: AbortSignal } = {}) =>
    request<{
      name: string;
      description: string;
      track_uris: string[];
      tracks: {
        id: string;
        uri: string;
        name: string;
        artists: string[];
        album: string | null;
        duration_ms: number;
        image_url: string | null;
        preview_url: string | null;
        explicit: boolean;
      }[];
      reasoning: string;
    }>("/curate/build", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, feedback }),
      signal: options.signal,
      timeoutMs: 180_000,
    }),
  curateSave: (sessionId: string, trackUris?: string[], options: { signal?: AbortSignal } = {}) =>
    request<{ playlist_id: string; name: string; tracks: number }>("/curate/save", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, track_uris: trackUris }),
      signal: options.signal,
      timeoutMs: 60_000,
    }),
  discoverGenerate: (options: { signal?: AbortSignal } = {}) =>
    request<DiscoverProposal>("/discover/generate", {
      method: "POST",
      signal: options.signal,
      timeoutMs: 180_000,
    }),
  discoverRun: (runId: string) => request<DiscoverProposal>(`/discover/runs/${runId}`),
  discoverSave: (runId: string, trackUris?: string[], options: { signal?: AbortSignal } = {}) =>
    request<DiscoverProposal>(`/discover/runs/${runId}/save`, {
      method: "POST",
      body: JSON.stringify({ track_uris: trackUris ?? [] }),
      signal: options.signal,
      timeoutMs: 120_000,
    }),
  discoverHistory: () => request<DiscoverHistoryItem[]>("/discover/history"),
  discoverDelete: (runId: string) =>
    request<{ status: string }>(`/discover/runs/${runId}`, { method: "DELETE" }),
  discoverRemove: (runId: string, payload: { remove_history: boolean; delete_playlist: boolean }) =>
    request<{ status: string }>(`/discover/runs/${runId}/remove`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
