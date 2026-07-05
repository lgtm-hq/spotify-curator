import { useEffect, useState } from "react";
import type { DiscoverHistoryItem } from "../../api/client";
import { UserFacingError } from "../UserFacingError";

export interface DiscoverRemoveChoice {
  removeHistory: boolean;
  deletePlaylist: boolean;
}

export function DiscoverRemoveDialog({
  run,
  removing,
  error,
  onClose,
  onConfirm,
}: {
  run: DiscoverHistoryItem;
  removing: boolean;
  error: unknown;
  onClose: () => void;
  onConfirm: (choice: DiscoverRemoveChoice) => void;
}) {
  const hasSpotifyPlaylist = Boolean(run.playlist_id);
  const [removeHistory, setRemoveHistory] = useState(true);
  const [deletePlaylist, setDeletePlaylist] = useState(false);

  useEffect(() => {
    setRemoveHistory(true);
    setDeletePlaylist(false);
  }, [run.run_id]);

  const canConfirm = removeHistory || deletePlaylist;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-white/10 bg-zinc-950 p-6 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4">
          <h3 className="text-lg font-semibold">Remove discovery run</h3>
          <p className="mt-1 text-sm text-zinc-500">
            Choose what to remove for <span className="text-zinc-300">{run.name}</span>.
          </p>
        </div>

        <div className="space-y-3">
          <label className="flex cursor-pointer gap-3 rounded-lg border border-white/10 bg-white/5 p-3">
            <input
              type="checkbox"
              checked={removeHistory}
              onChange={(event) => setRemoveHistory(event.target.checked)}
              disabled={removing}
              className="mt-0.5 rounded border-white/20 bg-black/30"
            />
            <span className="space-y-1">
              <span className="block text-sm font-medium text-zinc-200">
                Remove from Discover history
              </span>
              <span className="block text-xs text-zinc-500">
                Hides this run here and removes the Discover tag from the dashboard. The Spotify
                playlist is kept.
              </span>
            </span>
          </label>

          <label
            className={`flex gap-3 rounded-lg border border-white/10 bg-white/5 p-3 ${
              hasSpotifyPlaylist ? "cursor-pointer" : "cursor-not-allowed opacity-60"
            }`}
          >
            <input
              type="checkbox"
              checked={deletePlaylist}
              onChange={(event) => setDeletePlaylist(event.target.checked)}
              disabled={removing || !hasSpotifyPlaylist}
              className="mt-0.5 rounded border-white/20 bg-black/30"
            />
            <span className="space-y-1">
              <span className="block text-sm font-medium text-zinc-200">
                Delete playlist from Spotify
              </span>
              <span className="block text-xs text-zinc-500">
                {hasSpotifyPlaylist
                  ? "Removes the playlist from your library. This cannot be undone."
                  : "This run was never saved to Spotify."}
              </span>
            </span>
          </label>
        </div>

        {removeHistory && deletePlaylist && (
          <p className="mt-3 text-xs text-amber-200/90">
            Both selected: the run disappears from history and the playlist is removed from Spotify.
          </p>
        )}

        {!removeHistory && deletePlaylist && (
          <p className="mt-3 text-xs text-zinc-500">
            The run stays in history as dismissed, but without a linked Spotify playlist.
          </p>
        )}

        {error != null && (
          <div className="mt-4">
            <UserFacingError compact title="Remove failed" error={error} />
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={removing}
            className="rounded-lg border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={removing || !canConfirm}
            onClick={() =>
              onConfirm({
                removeHistory,
                deletePlaylist,
              })
            }
            className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm font-medium text-red-200 hover:bg-red-500/15 disabled:opacity-50"
          >
            {removing ? "Removing…" : "Confirm remove"}
          </button>
        </div>
      </div>
    </div>
  );
}
