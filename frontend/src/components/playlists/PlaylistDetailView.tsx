import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type CleanupAnalysis } from "../../api/client";
import { CleanupSummaryBanner } from "./CleanupIssueTags";
import { PlaylistTrackPanel } from "./PlaylistTrackPanel";
import type { PlaylistScanSummary } from "./cleanupInsights";

function trackIdsFromIssues(issues: { track_ids: string[] }[]): string[] {
  return issues.flatMap((issue) => issue.track_ids);
}

export function PlaylistDetailView({ playlistId }: { playlistId: string }) {
  const queryClient = useQueryClient();

  const scanSummaries = useQuery({
    queryKey: ["playlist-scan-summaries"],
    queryFn: api.playlistScanSummaries,
  });

  const cleanup = useQuery({
    queryKey: ["cleanup-analysis", playlistId],
    queryFn: () => api.cleanupAnalyze(playlistId),
    staleTime: 60_000,
  });

  const summary: PlaylistScanSummary | undefined = scanSummaries.data?.[playlistId];

  const removeTracks = useMutation({
    mutationFn: (trackIds: string[]) => api.cleanupRemove(playlistId, trackIds),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["cleanup-analysis", playlistId] });
      await queryClient.invalidateQueries({ queryKey: ["playlist", playlistId] });
      await queryClient.invalidateQueries({ queryKey: ["playlist-scan-summaries"] });
      await queryClient.invalidateQueries({ queryKey: ["playlists"] });
    },
  });

  const skipHeavyCount = cleanup.data ? trackIdsFromIssues(cleanup.data.skip_heavy).length : 0;

  return (
    <div className="space-y-4">
      <Link to="/" className="text-sm text-emerald-400 hover:underline">
        ← Back to playlists
      </Link>

      <div className="overflow-hidden rounded-xl border border-white/10 bg-black/20">
        <CleanupSummaryBanner
          summary={summary}
          skipHeavyCount={skipHeavyCount}
          busy={removeTracks.isPending}
          onRemoveDuplicates={
            cleanup.data
              ? () => removeTracks.mutate(trackIdsFromIssues(cleanup.data!.duplicates))
              : undefined
          }
          onRemoveUnavailable={
            cleanup.data
              ? () => removeTracks.mutate(trackIdsFromIssues(cleanup.data!.unavailable))
              : undefined
          }
          onRemoveSkipHeavy={
            cleanup.data
              ? () => removeTracks.mutate(trackIdsFromIssues(cleanup.data!.skip_heavy))
              : undefined
          }
        />
        <div className="h-[min(70vh,720px)]">
          <PlaylistTrackPanel
            playlistId={playlistId}
            compact
            cleanupAnalysis={cleanup.data}
            cleanupLoading={cleanup.isLoading}
          />
        </div>
      </div>
    </div>
  );
}

export type { CleanupAnalysis };
