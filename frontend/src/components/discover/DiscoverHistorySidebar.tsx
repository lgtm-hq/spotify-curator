import { Link } from "react-router-dom";
import type { DiscoverHistoryItem } from "../../api/client";

function statusBadgeClass(status: DiscoverHistoryItem["status"]): string {
  if (status === "saved") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
  }
  if (status === "dismissed") {
    return "border-zinc-500/30 bg-zinc-500/10 text-zinc-400";
  }
  return "border-sky-500/30 bg-sky-500/10 text-sky-200";
}

function statusLabel(status: DiscoverHistoryItem["status"]): string {
  if (status === "saved") {
    return "On Spotify";
  }
  if (status === "dismissed") {
    return "Dismissed";
  }
  return "Pending";
}

function spotifyPlaylistUrl(playlistId: string): string {
  return `https://open.spotify.com/playlist/${playlistId}`;
}

export function DiscoverHistorySidebar({
  runs,
  selectedRunId,
  loadingRunId,
  removingRunId,
  onSelect,
  onRemove,
}: {
  runs: DiscoverHistoryItem[];
  selectedRunId: string | null;
  loadingRunId: string | null;
  removingRunId: string | null;
  onSelect: (runId: string) => void;
  onRemove: (run: DiscoverHistoryItem) => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 px-4 py-3">
        <h3 className="text-sm font-medium text-zinc-200">Recent runs</h3>
        <p className="mt-0.5 text-xs text-zinc-500">{runs.length} saved proposals</p>
      </div>
      <ul className="flex-1 overflow-y-auto">
        {runs.map((run) => {
          const isSelected = selectedRunId === run.run_id;
          const isLoading = loadingRunId === run.run_id;
          const isRemoving = removingRunId === run.run_id;

          return (
            <li key={run.run_id} className="border-b border-white/5 last:border-b-0">
              <button
                type="button"
                disabled={isLoading || isRemoving}
                onClick={() => onSelect(run.run_id)}
                className={`group flex w-full items-start gap-3 px-4 py-3 text-left transition hover:bg-white/5 ${
                  isSelected ? "bg-emerald-500/10" : ""
                } ${isLoading || isRemoving ? "opacity-60" : ""}`}
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate font-medium text-zinc-100">{run.name}</p>
                    <span
                      className={`shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${statusBadgeClass(run.status)}`}
                    >
                      {statusLabel(run.status)}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-500">
                    {run.track_count} tracks · {new Date(run.created_at).toLocaleString()}
                  </p>
                  {run.legacy_auto_saved && (
                    <p className="text-[11px] text-zinc-600">Auto-saved before review flow</p>
                  )}
                </div>
                {isSelected && (
                  <span className="shrink-0 text-emerald-400" aria-hidden>
                    ›
                  </span>
                )}
              </button>
              <div className="flex flex-wrap gap-2 px-4 pb-3">
                {run.status === "saved" && run.playlist_id && (
                  <>
                    <Link
                      to={`/playlists/${run.playlist_id}`}
                      onClick={(event) => event.stopPropagation()}
                      className="rounded-md border border-emerald-400/30 px-2 py-1 text-xs text-emerald-300 hover:bg-emerald-500/10"
                    >
                      Open
                    </Link>
                    <a
                      href={spotifyPlaylistUrl(run.playlist_id)}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(event) => event.stopPropagation()}
                      className="rounded-md border border-white/10 px-2 py-1 text-xs text-zinc-400 hover:bg-white/5"
                    >
                      Spotify
                    </a>
                  </>
                )}
                <button
                  type="button"
                  disabled={isLoading || isRemoving}
                  onClick={() => onRemove(run)}
                  className="rounded-md border border-red-500/30 px-2 py-1 text-xs text-red-300 hover:bg-red-500/10 disabled:opacity-60"
                >
                  {isRemoving ? "Removing…" : "Remove"}
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
