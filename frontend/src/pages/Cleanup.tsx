import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";

type CleanupSuggestion = {
  playlist_id: string;
  playlist_name: string;
  priority?: "high" | "medium" | "low";
  kind?: string;
  title: string;
  description: string;
  recommended_action: string;
};

type AiSuggestResult = {
  summary: string;
  scanned_playlists: number;
  total_playlists: number;
  suggestions: CleanupSuggestion[];
};

export function Cleanup() {
  const playlists = useQuery({ queryKey: ["playlists"], queryFn: api.playlists });
  const [selectedId, setSelectedId] = useState("");
  const [analysis, setAnalysis] = useState<Record<string, unknown> | null>(null);
  const [aiSuggestions, setAiSuggestions] = useState<AiSuggestResult | null>(null);

  const analyze = useMutation({
    mutationFn: (id: string) => api.cleanupAnalyze(id),
    onSuccess: setAnalysis,
  });

  const aiSuggest = useMutation({
    mutationFn: () => api.cleanupAiSuggest(),
    onSuccess: setAiSuggestions,
  });

  const remove = useMutation({
    mutationFn: ({ playlistId, trackIds }: { playlistId: string; trackIds: string[] }) =>
      api.cleanupRemove(playlistId, trackIds),
  });

  const split = useMutation({
    mutationFn: ({ playlistId, proposals }: { playlistId: string; proposals: unknown[] }) =>
      api.cleanupSplit(playlistId, proposals),
  });

  const runAnalyzeForPlaylist = (playlistId: string) => {
    setSelectedId(playlistId);
    setAnalysis(null);
    analyze.mutate(playlistId);
  };

  const duplicateIds = [
    ...((analysis?.duplicates as { track_ids: string[] }[]) ?? []).flatMap((d) => d.track_ids),
  ];
  const unavailableIds = [
    ...((analysis?.unavailable as { track_ids: string[] }[]) ?? []).flatMap((d) => d.track_ids),
  ];
  const skipIds = [
    ...((analysis?.skip_heavy as { track_ids: string[] }[]) ?? []).flatMap((d) => d.track_ids),
  ];
  const clusters =
    (analysis?.clusters as {
      name: string;
      track_ids: string[];
      cluster_label: string;
    }[]) ?? [];

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-semibold">Playlist Cleanup</h2>
        <p className="mt-1 text-sm text-zinc-400">
          Scan individual playlists or let AI review your library for cleanup opportunities.
        </p>
      </div>

      <section className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-5">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-medium text-violet-200">AI Cleanup Advisor</h3>
            <p className="mt-1 max-w-2xl text-sm text-zinc-400">
              Scans your largest playlists for duplicates and dead tracks, then suggests
              prioritized cleanups based on your taste profile.
            </p>
          </div>
          <button
            type="button"
            disabled={aiSuggest.isPending}
            onClick={() => aiSuggest.mutate()}
            className="rounded-lg bg-violet-500 px-4 py-2 font-medium text-black disabled:opacity-50"
          >
            {aiSuggest.isPending ? "Scanning library…" : "Scan my library"}
          </button>
        </div>

        {aiSuggest.isError && (
          <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {aiSuggest.error instanceof Error
              ? aiSuggest.error.message
              : "Could not generate cleanup suggestions."}
          </p>
        )}

        {aiSuggest.isPending && (
          <div className="space-y-3">
            <div className="h-4 w-2/3 animate-pulse rounded bg-white/10" />
            <div className="h-20 animate-pulse rounded-lg bg-white/5" />
            <div className="h-20 animate-pulse rounded-lg bg-white/5" />
          </div>
        )}

        {aiSuggestions && !aiSuggest.isPending && (
          <div className="space-y-4">
            <p className="text-sm text-zinc-300">{aiSuggestions.summary}</p>
            <p className="text-xs text-zinc-500">
              Scanned {aiSuggestions.scanned_playlists} of {aiSuggestions.total_playlists}{" "}
              playlists
            </p>

            {aiSuggestions.suggestions.length === 0 ? (
              <p className="rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-zinc-400">
                No cleanup suggestions right now — your scanned playlists look tidy.
              </p>
            ) : (
              <ul className="space-y-3">
                {aiSuggestions.suggestions.map((suggestion) => (
                  <li
                    key={`${suggestion.playlist_id}-${suggestion.title}`}
                    className="rounded-lg border border-white/10 bg-black/20 p-4"
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      {suggestion.priority && (
                        <PriorityBadge priority={suggestion.priority} />
                      )}
                      {suggestion.kind && (
                        <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-zinc-400">
                          {suggestion.kind}
                        </span>
                      )}
                    </div>
                    <h4 className="font-medium">{suggestion.title}</h4>
                    <p className="mt-1 text-sm text-zinc-400">{suggestion.description}</p>
                    <p className="mt-2 text-xs text-zinc-500">{suggestion.recommended_action}</p>
                    <button
                      type="button"
                      disabled={analyze.isPending && selectedId === suggestion.playlist_id}
                      onClick={() => runAnalyzeForPlaylist(suggestion.playlist_id)}
                      className="mt-3 rounded-lg border border-violet-500/40 px-3 py-1.5 text-sm text-violet-300 hover:bg-violet-500/10 disabled:opacity-50"
                    >
                      {analyze.isPending && selectedId === suggestion.playlist_id
                        ? "Analyzing…"
                        : `Analyze "${suggestion.playlist_name}"`}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      <section className="space-y-4">
        <h3 className="text-lg font-medium">Manual playlist scan</h3>
        <div className="flex flex-wrap gap-3">
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            className="rounded-lg border border-white/10 bg-black px-3 py-2"
          >
            <option value="">Select playlist</option>
            {(playlists.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!selectedId || analyze.isPending}
            onClick={() => runAnalyzeForPlaylist(selectedId)}
            className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black disabled:opacity-50"
          >
            {analyze.isPending ? "Analyzing…" : "Analyze"}
          </button>
        </div>

        {analysis && (
          <div className="space-y-4">
            <p className="text-zinc-400">{String(analysis.total_tracks)} tracks analyzed</p>

            <CleanupSection
              title="Duplicates"
              count={duplicateIds.length}
              onApply={() => remove.mutate({ playlistId: selectedId, trackIds: duplicateIds })}
            />
            <CleanupSection
              title="Unavailable"
              count={unavailableIds.length}
              onApply={() =>
                remove.mutate({
                  playlistId: selectedId,
                  trackIds: unavailableIds,
                })
              }
            />
            <CleanupSection
              title="Skip-heavy"
              count={skipIds.length}
              onApply={() => remove.mutate({ playlistId: selectedId, trackIds: skipIds })}
            />

            {clusters.length > 0 && (
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <h3 className="mb-2 font-medium">Split proposals</h3>
                <ul className="mb-4 space-y-1 text-sm text-zinc-400">
                  {clusters.map((c) => (
                    <li key={c.cluster_label}>
                      {c.cluster_label}: {c.track_ids.length} tracks
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={() => split.mutate({ playlistId: selectedId, proposals: clusters })}
                  className="rounded-lg border border-emerald-500/40 px-4 py-2 text-emerald-300"
                >
                  Create split playlists
                </button>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function PriorityBadge({ priority }: { priority: "high" | "medium" | "low" }) {
  const styles = {
    high: "bg-red-500/20 text-red-300",
    medium: "bg-amber-500/20 text-amber-300",
    low: "bg-zinc-500/20 text-zinc-300",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[priority]}`}>
      {priority}
    </span>
  );
}

function CleanupSection({
  title,
  count,
  onApply,
}: {
  title: string;
  count: number;
  onApply: () => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-4">
      <div>
        <h3 className="font-medium">{title}</h3>
        <p className="text-sm text-zinc-400">{count} tracks flagged</p>
      </div>
      <button
        type="button"
        disabled={count === 0}
        onClick={onApply}
        className="rounded-lg bg-red-500/20 px-4 py-2 text-red-300 disabled:opacity-40"
      >
        Remove
      </button>
    </div>
  );
}
