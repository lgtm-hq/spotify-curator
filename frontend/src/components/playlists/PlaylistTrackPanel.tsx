import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type TrackSummary } from "../../api/client";
import { formatDuration, reorderPayload } from "./viewMode";

export function PlaylistTrackPanel({
  playlistId,
  compact = false,
}: {
  playlistId: string;
  compact?: boolean;
}) {
  const queryClient = useQueryClient();
  const detail = useQuery({
    queryKey: ["playlist", playlistId],
    queryFn: () => api.playlist(playlistId),
  });

  const removeTrack = useMutation({
    mutationFn: (trackId: string) => api.playlistRemoveTracks(playlistId, [trackId]),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["playlist", playlistId] });
      await queryClient.invalidateQueries({ queryKey: ["playlists"] });
    },
  });

  const moveTrack = useMutation({
    mutationFn: (payload: { range_start: number; insert_before: number }) =>
      api.playlistReorderTracks(playlistId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["playlist", playlistId] });
    },
  });

  if (detail.isLoading) {
    return (
      <div className="space-y-2 p-4">
        <div className="h-6 w-1/3 animate-pulse rounded bg-white/10" />
        <div className="h-12 animate-pulse rounded bg-white/5" />
        <div className="h-12 animate-pulse rounded bg-white/5" />
      </div>
    );
  }

  if (detail.isError || !detail.data) {
    return (
      <p className="p-4 text-sm text-red-300">
        {detail.error instanceof Error ? detail.error.message : "Failed to load playlist."}
      </p>
    );
  }

  const playlist = detail.data;
  const canEdit = playlist.can_edit;

  const handleMove = (fromIndex: number, toIndex: number) => {
    const payload = reorderPayload(fromIndex, toIndex);
    if (payload) {
      moveTrack.mutate(payload);
    }
  };

  return (
    <div className={`flex h-full flex-col ${compact ? "" : "min-h-0"}`}>
      <div className="border-b border-white/10 px-4 py-3">
        <div className="flex items-center gap-3">
          {playlist.image_url ? (
            <img
              src={playlist.image_url}
              alt=""
              className="h-12 w-12 rounded-md object-cover"
            />
          ) : (
            <div className="flex h-12 w-12 items-center justify-center rounded-md bg-zinc-800 text-zinc-500">
              ♫
            </div>
          )}
          <div className="min-w-0">
            <h3 className="truncate font-medium">{playlist.name}</h3>
            <p className="text-sm text-zinc-400">
              {playlist.tracks.length} tracks · {playlist.owner}
              {!canEdit && " · read-only"}
            </p>
          </div>
        </div>
        {playlist.description && (
          <p className="mt-2 line-clamp-2 text-sm text-zinc-500">{playlist.description}</p>
        )}
      </div>

      <ul className="flex-1 overflow-y-auto divide-y divide-white/5">
        {playlist.tracks.length === 0 && (
          <li className="px-4 py-8 text-center text-sm text-zinc-500">No tracks in playlist.</li>
        )}
        {playlist.tracks.map((track, index) => (
          <TrackRow
            key={`${track.id}-${index}`}
            track={track}
            index={index}
            total={playlist.tracks.length}
            canEdit={canEdit}
            busy={removeTrack.isPending || moveTrack.isPending}
            onRemove={() => removeTrack.mutate(track.id)}
            onMoveUp={() => handleMove(index, index - 1)}
            onMoveDown={() => handleMove(index, index + 1)}
          />
        ))}
      </ul>
    </div>
  );
}

function TrackRow({
  track,
  index,
  total,
  canEdit,
  busy,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  track: TrackSummary;
  index: number;
  total: number;
  canEdit: boolean;
  busy: boolean;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const artistNames = track.artists.map((artist) => artist.name).join(", ");

  return (
    <li className="group flex items-center gap-3 px-4 py-2.5 hover:bg-white/5">
      <span className="w-6 shrink-0 text-center text-xs text-zinc-600">{index + 1}</span>
      {track.album_image_url ? (
        <img src={track.album_image_url} alt="" className="h-10 w-10 rounded object-cover" />
      ) : (
        <div className="flex h-10 w-10 items-center justify-center rounded bg-zinc-800 text-xs text-zinc-600">
          ♪
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className={`truncate text-sm ${track.is_playable ? "text-zinc-100" : "text-zinc-500"}`}>
          {track.name}
        </p>
        <p className="truncate text-xs text-zinc-500">
          {artistNames}
          {track.album ? ` · ${track.album}` : ""}
        </p>
      </div>
      <span className="shrink-0 text-xs text-zinc-500">{formatDuration(track.duration_ms)}</span>
      {canEdit && (
        <div className="flex shrink-0 items-center gap-1 opacity-100 transition md:opacity-0 md:group-hover:opacity-100">
          <IconButton
            label="Move up"
            disabled={busy || index === 0}
            onClick={onMoveUp}
          >
            ↑
          </IconButton>
          <IconButton
            label="Move down"
            disabled={busy || index >= total - 1}
            onClick={onMoveDown}
          >
            ↓
          </IconButton>
          <IconButton label="Remove track" disabled={busy} onClick={onRemove} danger>
            ✕
          </IconButton>
        </div>
      )}
    </li>
  );
}

function IconButton({
  children,
  label,
  disabled,
  onClick,
  danger = false,
}: {
  children: string;
  label: string;
  disabled?: boolean;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={`rounded px-2 py-1 text-xs disabled:opacity-30 ${
        danger
          ? "text-red-300 hover:bg-red-500/10"
          : "text-zinc-400 hover:bg-white/10 hover:text-zinc-200"
      }`}
    >
      {children}
    </button>
  );
}

export function PlaylistTrackPanelPlaceholder() {
  return (
    <div className="flex h-full flex-col items-center justify-center p-8 text-center text-zinc-500">
      <p className="text-lg">Select a playlist</p>
      <p className="mt-1 text-sm">Tracks will appear here</p>
    </div>
  );
}
