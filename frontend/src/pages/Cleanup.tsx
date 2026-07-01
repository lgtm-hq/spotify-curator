import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";

export function Cleanup() {
  const playlists = useQuery({ queryKey: ["playlists"], queryFn: api.playlists });
  const [selectedId, setSelectedId] = useState("");
  const [analysis, setAnalysis] = useState<Record<string, unknown> | null>(null);

  const analyze = useMutation({
    mutationFn: (id: string) => api.cleanupAnalyze(id),
    onSuccess: setAnalysis,
  });

  const remove = useMutation({
    mutationFn: ({ playlistId, trackIds }: { playlistId: string; trackIds: string[] }) =>
      api.cleanupRemove(playlistId, trackIds),
  });

  const split = useMutation({
    mutationFn: ({ playlistId, proposals }: { playlistId: string; proposals: unknown[] }) =>
      api.cleanupSplit(playlistId, proposals),
  });

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
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">Playlist Cleanup</h2>
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
          onClick={() => analyze.mutate(selectedId)}
          className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black disabled:opacity-50"
        >
          Analyze
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
    </div>
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
