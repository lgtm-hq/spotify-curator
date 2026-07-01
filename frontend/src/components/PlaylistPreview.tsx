export interface CurateTrack {
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

export interface CurateProposal {
  name: string;
  description: string;
  track_uris: string[];
  tracks: CurateTrack[];
  reasoning: string;
}

function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

interface PlaylistPreviewProps {
  tracks: CurateTrack[];
  onRemove: (trackId: string) => void;
}

export function PlaylistPreview({ tracks, onRemove }: PlaylistPreviewProps) {
  return (
    <details open className="group rounded-xl border border-white/10 bg-black/30">
      <summary className="cursor-pointer list-none px-4 py-3 marker:content-none">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="font-medium text-zinc-100">Playlist preview</p>
            <p className="text-sm text-zinc-400">
              {tracks.length} track{tracks.length === 1 ? "" : "s"} · expand to review
            </p>
          </div>
          <span className="text-sm text-emerald-400 transition group-open:rotate-180">▾</span>
        </div>
      </summary>

      <div className="divide-y divide-white/5 border-t border-white/10">
        {tracks.map((track) => (
          <details key={track.id} className="px-4 py-3">
            <summary className="cursor-pointer list-none marker:content-none">
              <div className="flex items-center gap-3">
                {track.image_url ? (
                  <img
                    src={track.image_url}
                    alt=""
                    className="h-12 w-12 rounded-md object-cover"
                  />
                ) : (
                  <div className="flex h-12 w-12 items-center justify-center rounded-md bg-zinc-800 text-xs text-zinc-500">
                    No art
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-zinc-100">{track.name}</p>
                  <p className="truncate text-sm text-zinc-400">
                    {track.artists.join(", ")}
                    {track.album ? ` · ${track.album}` : ""}
                  </p>
                </div>
                <span className="shrink-0 text-sm text-zinc-500">
                  {formatDuration(track.duration_ms)}
                </span>
              </div>
            </summary>

            <div className="mt-3 space-y-2 rounded-lg bg-white/5 p-3 text-sm text-zinc-300">
              <p>
                <span className="text-zinc-500">Album:</span> {track.album ?? "Unknown"}
              </p>
              <p>
                <span className="text-zinc-500">Duration:</span>{" "}
                {formatDuration(track.duration_ms)}
              </p>
              <p>
                <span className="text-zinc-500">Explicit:</span> {track.explicit ? "Yes" : "No"}
              </p>
              <p className="break-all">
                <span className="text-zinc-500">URI:</span> {track.uri}
              </p>
              <div className="flex flex-wrap gap-2 pt-1">
                <a
                  href={`https://open.spotify.com/track/${track.id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-emerald-300 transition hover:bg-white/5"
                >
                  Open in Spotify
                </a>
                {track.preview_url && (
                  <a
                    href={track.preview_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-white/5"
                  >
                    Preview clip
                  </a>
                )}
                <button
                  type="button"
                  onClick={() => onRemove(track.id)}
                  className="rounded-md border border-red-500/30 px-3 py-1.5 text-xs text-red-300 transition hover:bg-red-500/10"
                >
                  Remove
                </button>
              </div>
            </div>
          </details>
        ))}
      </div>
    </details>
  );
}
