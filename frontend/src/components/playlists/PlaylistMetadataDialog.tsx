import { useEffect, useState } from "react";
import type { PlaylistSummary } from "../../api/client";
import { UserFacingError } from "../UserFacingError";

export function PlaylistMetadataDialog({
  playlist,
  saving,
  error,
  onClose,
  onSave,
}: {
  playlist: PlaylistSummary;
  saving: boolean;
  error: unknown;
  onClose: () => void;
  onSave: (payload: { name: string; description: string; public: boolean }) => void;
}) {
  const [name, setName] = useState(playlist.name);
  const [description, setDescription] = useState(playlist.description ?? "");
  const [isPublic, setIsPublic] = useState(playlist.public);

  useEffect(() => {
    setName(playlist.name);
    setDescription(playlist.description ?? "");
    setIsPublic(playlist.public);
  }, [playlist]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-white/10 bg-zinc-950 p-6 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold">Edit playlist</h3>
            <p className="mt-1 text-sm text-zinc-500">
              Update name, description, and visibility on Spotify.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-lg border border-white/10 px-2 py-1 text-sm text-zinc-400 hover:bg-white/5 disabled:opacity-50"
          >
            Close
          </button>
        </div>

        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            onSave({
              name: name.trim(),
              description: description.trim(),
              public: isPublic,
            });
          }}
        >
          <label className="block space-y-1.5">
            <span className="text-sm text-zinc-300">Name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={saving}
              maxLength={100}
              className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-zinc-100 outline-none ring-emerald-500/40 focus:ring-2"
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm text-zinc-300">Description</span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              disabled={saving}
              rows={3}
              maxLength={300}
              className="w-full resize-none rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-zinc-100 outline-none ring-emerald-500/40 focus:ring-2"
            />
          </label>

          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input
              type="checkbox"
              checked={isPublic}
              onChange={(event) => setIsPublic(event.target.checked)}
              disabled={saving}
              className="rounded border-white/20 bg-black/30"
            />
            Public on Spotify
          </label>

          {error != null && (
            <UserFacingError compact title="Could not save playlist" error={error} />
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !name.trim()}
              className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
