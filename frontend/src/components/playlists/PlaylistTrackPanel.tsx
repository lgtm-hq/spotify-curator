import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type CleanupAnalysis,
  type PlaylistDetail,
  type TrackSummary,
} from "../../api/client";
import { cleanupTagStyles, issueRowClass, type CleanupIssueKind } from "./cleanupInsights";
import { formatDuration, reorderPayload } from "./viewMode";
import { UserFacingError } from "../UserFacingError";

function trackIssueMap(analysis: CleanupAnalysis | undefined): Map<string, CleanupIssueKind[]> {
  const map = new Map<string, CleanupIssueKind[]>();
  if (!analysis) {
    return map;
  }

  const add = (ids: string[], kind: CleanupIssueKind) => {
    for (const id of ids) {
      const existing = map.get(id) ?? [];
      if (!existing.includes(kind)) {
        map.set(id, [...existing, kind]);
      }
    }
  };

  for (const issue of analysis.duplicates) {
    add(issue.track_ids, "duplicates");
  }
  for (const issue of analysis.unavailable) {
    add(issue.track_ids, "unavailable");
  }
  for (const issue of analysis.skip_heavy) {
    add(issue.track_ids, "skip-heavy");
  }

  return map;
}

function reorderTracksLocally(
  tracks: TrackSummary[],
  fromIndex: number,
  toIndex: number,
): TrackSummary[] {
  const next = [...tracks];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved);
  return next;
}

export function PlaylistTrackPanel({
  playlistId,
  compact = false,
  cleanupAnalysis,
  cleanupLoading = false,
}: {
  playlistId: string;
  compact?: boolean;
  cleanupAnalysis?: CleanupAnalysis;
  cleanupLoading?: boolean;
}) {
  const queryClient = useQueryClient();
  const detail = useQuery({
    queryKey: ["playlist", playlistId],
    queryFn: () => api.playlist(playlistId),
  });

  const removeTrack = useMutation({
    mutationFn: ({ trackUri }: { trackId: string; trackUri: string }) =>
      api.playlistRemoveTracks(playlistId, {
        track_ids: [],
        track_uris: [trackUri],
      }),
    onMutate: async ({ trackId }) => {
      await queryClient.cancelQueries({ queryKey: ["playlist", playlistId] });
      const previous = queryClient.getQueryData<PlaylistDetail>(["playlist", playlistId]);
      if (previous) {
        queryClient.setQueryData<PlaylistDetail>(["playlist", playlistId], {
          ...previous,
          tracks: previous.tracks.filter((track) => track.id !== trackId),
          track_count: Math.max(0, previous.track_count - 1),
        });
      }
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["playlist", playlistId], context.previous);
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["cleanup-analysis", playlistId] });
      await queryClient.invalidateQueries({ queryKey: ["playlist-scan-summaries"] });
    },
  });

  const moveTrack = useMutation({
    mutationFn: ({
      range_start,
      insert_before,
      range_length,
    }: {
      fromIndex: number;
      toIndex: number;
      range_start: number;
      insert_before: number;
      range_length: number;
    }) => api.playlistReorderTracks(playlistId, { range_start, insert_before, range_length }),
    onMutate: async ({ fromIndex, toIndex }) => {
      await queryClient.cancelQueries({ queryKey: ["playlist", playlistId] });
      const previous = queryClient.getQueryData<PlaylistDetail>(["playlist", playlistId]);
      if (previous) {
        queryClient.setQueryData<PlaylistDetail>(["playlist", playlistId], {
          ...previous,
          tracks: reorderTracksLocally(previous.tracks, fromIndex, toIndex),
        });
      }
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["playlist", playlistId], context.previous);
      }
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
      <div className="p-4">
        <UserFacingError
          compact
          title="Couldn't load tracks"
          error={detail.error}
          fallback="This playlist couldn't be loaded right now."
          onRetry={() => void detail.refetch()}
          retryLabel="Retry"
        />
      </div>
    );
  }

  const playlist = detail.data;
  const canEdit = playlist.can_edit;
  const trackIssues = trackIssueMap(cleanupAnalysis);

  const handleMove = (fromIndex: number, toIndex: number) => {
    const payload = reorderPayload(fromIndex, toIndex);
    if (payload) {
      moveTrack.mutate({ fromIndex, toIndex, ...payload, range_length: 1 });
    }
  };

  return (
    <div className={`flex h-full flex-col ${compact ? "" : "min-h-0"}`}>
      <div className="border-b border-white/10 px-4 py-3">
        <div className="flex items-center gap-3">
          {playlist.image_url ? (
            <img src={playlist.image_url} alt="" className="h-12 w-12 rounded-md object-cover" />
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
              {cleanupLoading && " · analyzing…"}
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
            issues={trackIssues.get(track.id) ?? []}
            onRemove={() => removeTrack.mutate({ trackId: track.id, trackUri: track.uri })}
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
  issues,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  track: TrackSummary;
  index: number;
  total: number;
  canEdit: boolean;
  busy: boolean;
  issues: CleanupIssueKind[];
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const artistNames = track.artists.map((artist) => artist.name).join(", ");
  const rowHighlight = issueRowClass(issues);

  return (
    <li className={`group flex items-center gap-3 px-4 py-2.5 hover:bg-white/5 ${rowHighlight}`}>
      <span className="w-6 shrink-0 text-center text-xs text-zinc-600">{index + 1}</span>
      {track.album_image_url ? (
        <img src={track.album_image_url} alt="" className="h-10 w-10 rounded object-cover" />
      ) : (
        <div className="flex h-10 w-10 items-center justify-center rounded bg-zinc-800 text-xs text-zinc-600">
          ♪
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p
            className={`truncate text-sm ${track.is_playable ? "text-zinc-100" : "text-zinc-500"}`}
          >
            {track.name}
          </p>
          {issues.map((kind) => (
            <span
              key={kind}
              className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] ${cleanupTagStyles[kind].className}`}
            >
              {cleanupTagStyles[kind].label}
            </span>
          ))}
        </div>
        <p className="truncate text-xs text-zinc-500">
          {artistNames}
          {track.album ? ` · ${track.album}` : ""}
        </p>
      </div>
      <span className="shrink-0 text-xs text-zinc-500">{formatDuration(track.duration_ms)}</span>
      {canEdit && (
        <div className="flex shrink-0 items-center gap-1 opacity-100 transition md:opacity-0 md:group-hover:opacity-100">
          <IconButton label="Move up" disabled={busy || index === 0} onClick={onMoveUp}>
            ↑
          </IconButton>
          <IconButton label="Move down" disabled={busy || index >= total - 1} onClick={onMoveDown}>
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
