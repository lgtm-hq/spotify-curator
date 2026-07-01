const API_BASE = "";

async function parseErrorDetail(
  response: Response,
  fallback: string,
): Promise<string> {
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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Request failed: ${response.status}`),
    );
  }
  return response.json() as Promise<T>;
}

export interface PlaylistSummary {
  id: string;
  name: string;
  description: string | null;
  owner: string;
  track_count: number;
  image_url: string | null;
  public: boolean;
}

export interface TasteProfile {
  summary: string;
  genres: string[];
  mood_tags: string[];
  era_preference: string;
  energy_range: string;
}

export const api = {
  me: () => request<{ user_id: string }>("/auth/me"),
  login: () => {
    window.location.href = "/auth/login";
  },
  playlists: () => request<PlaylistSummary[]>("/playlists"),
  taste: (refresh = false) => request<TasteProfile>(`/taste?refresh=${refresh}`),
  cleanupAnalyze: (playlistId: string) =>
    request<Record<string, unknown>>(`/cleanup/analyze/${playlistId}`, {
      method: "POST",
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
  curateStart: () =>
    request<{
      session_id: string;
      done: boolean;
      question?: string;
      options?: string[];
      playlist_brief?: string;
    }>("/curate/start", { method: "POST" }),
  curateAnswer: (sessionId: string, answer: string) =>
    request<{
      session_id: string;
      done: boolean;
      question?: string;
      options?: string[];
      playlist_brief?: string;
    }>("/curate/answer", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, answer }),
    }),
  curateBuild: (sessionId: string, feedback?: string) =>
    request<{
      name: string;
      description: string;
      track_uris: string[];
      reasoning: string;
    }>("/curate/build", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, feedback }),
    }),
  curateSave: (sessionId: string) =>
    request<{ playlist_id: string; name: string; tracks: number }>("/curate/save", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    }),
  discoverGenerate: () =>
    request<{
      run_id: string;
      playlist_id: string;
      name: string;
      track_count: number;
      reasoning: string;
    }>("/discover/generate", { method: "POST" }),
  discoverHistory: () =>
    request<
      {
        run_id: string;
        playlist_id: string | null;
        name: string;
        created_at: string;
      }[]
    >("/discover/history"),
};
