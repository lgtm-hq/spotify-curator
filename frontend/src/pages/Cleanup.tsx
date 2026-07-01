import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  api,
  type CleanupAiSuggestResult,
  type CleanupAnalysis,
  type CleanupCluster,
  type CleanupSuggestion,
} from "../api/client";

function trackIdsFromIssues(issues: { track_ids: string[] }[]): string[] {
  return issues.flatMap((issue) => issue.track_ids);
}

export function Cleanup() {
  const queryClient = useQueryClient();
  const playlists = useQuery({ queryKey: ["playlists"], queryFn: api.playlists });
  const [selectedId, setSelectedId] = useState("");
  const [aiSuggestions, setAiSuggestions] = useState<CleanupAiSuggestResult | null>(null);
  const [scanStartedAt, setScanStartedAt] = useState<number | null>(null);
  const [scanJobId, setScanJobId] = useState<string | null>(null);

  const aiSuggest = useMutation({
    mutationFn: () => api.cleanupAiSuggestStart(),
    onMutate: () => {
      setScanStartedAt(Date.now());
      setAiSuggestions(null);
      setScanJobId(null);
    },
    onSuccess: (result) => {
      setScanJobId(result.job_id);
    },
    onError: () => {
      setScanStartedAt(null);
      setScanJobId(null);
    },
  });

  const scanJob = useQuery({
    queryKey: ["cleanup-suggest-job", scanJobId],
    queryFn: () => api.cleanupAiSuggestJob(scanJobId!),
    enabled: Boolean(scanJobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") {
        return false;
      }
      return 1000;
    },
  });

  useEffect(() => {
    if (scanJob.data?.status === "completed" && scanJob.data.result) {
      setAiSuggestions(scanJob.data.result);
      setScanJobId(null);
      setScanStartedAt(null);
    }
    if (scanJob.data?.status === "failed") {
      setScanJobId(null);
      setScanStartedAt(null);
    }
  }, [scanJob.data]);

  const manualAnalysis = useQuery({
    queryKey: ["cleanup-analysis", selectedId],
    queryFn: () => api.cleanupAnalyze(selectedId),
    enabled: false,
  });

  const remove = useMutation({
    mutationFn: ({ playlistId, trackIds }: { playlistId: string; trackIds: string[] }) =>
      api.cleanupRemove(playlistId, trackIds),
    onSuccess: async (_, { playlistId }) => {
      await queryClient.invalidateQueries({ queryKey: ["cleanup-analysis", playlistId] });
      await queryClient.invalidateQueries({ queryKey: ["playlists"] });
    },
  });

  const split = useMutation({
    mutationFn: ({
      playlistId,
      proposals,
    }: {
      playlistId: string;
      proposals: CleanupCluster[];
    }) => api.cleanupSplit(playlistId, proposals),
    onSuccess: async (_, { playlistId }) => {
      await queryClient.invalidateQueries({ queryKey: ["cleanup-analysis", playlistId] });
    },
  });

  const runManualAnalyze = async () => {
    if (!selectedId) {
      return;
    }
    await manualAnalysis.refetch();
  };

  const cachedManualResult = selectedId
    ? queryClient.getQueryData<CleanupAnalysis>(["cleanup-analysis", selectedId])
    : undefined;
  const manualResult = manualAnalysis.data ?? cachedManualResult;

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
            disabled={aiSuggest.isPending || Boolean(scanJobId)}
            onClick={() => aiSuggest.mutate()}
            className="rounded-lg bg-violet-500 px-4 py-2 font-medium text-black disabled:opacity-50"
          >
            {aiSuggest.isPending || scanJobId ? "Scanning library…" : "Scan my library"}
          </button>
        </div>

        {(scanJob.data?.status === "failed" || scanJob.isError) && (
          <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {scanJob.data?.error ??
              (scanJob.error instanceof Error
                ? scanJob.error.message
                : "Could not generate cleanup suggestions.")}
          </p>
        )}

        {aiSuggest.isError && (
          <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {aiSuggest.error instanceof Error
              ? aiSuggest.error.message
              : "Could not start cleanup scan."}
          </p>
        )}

        {(aiSuggest.isPending || scanJobId) && (
          <ScanProgress
            startedAt={scanStartedAt ?? Date.now()}
            progress={scanJob.data?.progress}
          />
        )}

        {aiSuggestions && !scanJobId && !aiSuggest.isPending && (
          <div className="space-y-4">
            <p className="text-sm text-zinc-300">{aiSuggestions.summary}</p>
            <p className="text-xs text-zinc-500">
              Scanned {aiSuggestions.scanned_playlists} of {aiSuggestions.total_playlists}{" "}
              playlists · expand a suggestion for full analysis
            </p>

            {aiSuggestions.suggestions.length === 0 ? (
              <p className="rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-zinc-400">
                No cleanup suggestions right now — your scanned playlists look tidy.
              </p>
            ) : (
              <ul className="space-y-3">
                {aiSuggestions.suggestions.map((suggestion, index) => (
                  <SuggestionCard
                    key={`${suggestion.playlist_id}-${suggestion.title}-${index}`}
                    suggestion={suggestion}
                    removePending={remove.isPending}
                    splitPending={split.isPending}
                    onRemove={(trackIds) =>
                      remove.mutate({
                        playlistId: suggestion.playlist_id,
                        trackIds,
                      })
                    }
                    onSplit={(proposals) =>
                      split.mutate({
                        playlistId: suggestion.playlist_id,
                        proposals,
                      })
                    }
                  />
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      <section className="space-y-4">
        <h3 className="text-lg font-medium">Manual playlist scan</h3>
        <p className="text-sm text-zinc-500">
          Pick any playlist not covered by the AI suggestions above.
        </p>
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
            disabled={!selectedId || manualAnalysis.isFetching}
            onClick={() => void runManualAnalyze()}
            className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black disabled:opacity-50"
          >
            {manualAnalysis.isFetching ? "Analyzing…" : "Analyze"}
          </button>
        </div>

        {selectedId && manualAnalysis.isFetching && (
          <AnalysisSkeleton label="Analyzing playlist…" />
        )}

        {manualResult && selectedId && !manualAnalysis.isFetching && (
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="mb-4 text-sm text-zinc-400">
              {manualResult.total_tracks} tracks analyzed
            </p>
            <AnalysisActions
              playlistId={selectedId}
              analysis={manualResult}
              removePending={remove.isPending}
              splitPending={split.isPending}
              onRemove={(trackIds) => remove.mutate({ playlistId: selectedId, trackIds })}
              onSplit={(proposals) => split.mutate({ playlistId: selectedId, proposals })}
            />
          </div>
        )}
      </section>
    </div>
  );
}

function ScanProgress({
  startedAt,
  progress,
}: {
  startedAt: number;
  progress?: {
    phase: string;
    playlist_index: number;
    playlist_total: number;
    playlist_name: string;
    track_total: number;
    tracks_loaded: number;
    playlists_completed: number;
  };
}) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    const timer = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [startedAt]);

  let stage = "Preparing library scan…";
  if (progress?.phase === "ai") {
    stage = "Generating AI cleanup suggestions from full scan results…";
  } else if (progress?.playlist_name) {
    const trackLabel =
      progress.track_total > 0
        ? `${progress.tracks_loaded}/${progress.track_total} tracks`
        : `${progress.tracks_loaded} tracks loaded`;
    stage = `Scanning "${progress.playlist_name}" (${trackLabel}) — playlist ${progress.playlist_index}/${progress.playlist_total}`;
  }

  const completed = progress?.playlists_completed ?? 0;
  const total = progress?.playlist_total ?? 0;
  const percent =
    total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : undefined;

  return (
    <div className="space-y-3 rounded-lg border border-violet-500/20 bg-black/20 p-4">
      <p className="text-sm text-violet-200">{stage}</p>
      <p className="text-xs text-zinc-500">
        {elapsed}s elapsed
        {total > 0 ? ` · ${completed}/${total} playlists complete` : ""}
      </p>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-violet-500/70 transition-all duration-500"
          style={{ width: `${percent ?? 33}%` }}
        />
      </div>
      <p className="text-xs text-zinc-500">
        Full scans run in parallel and cached for an hour — AI only receives summary
        stats, not every track.
      </p>
    </div>
  );
}

function SuggestionCard({
  suggestion,
  removePending,
  splitPending,
  onRemove,
  onSplit,
}: {
  suggestion: CleanupSuggestion;
  removePending: boolean;
  splitPending: boolean;
  onRemove: (trackIds: string[]) => void;
  onSplit: (proposals: CleanupCluster[]) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const analysis = useQuery({
    queryKey: ["cleanup-analysis", suggestion.playlist_id],
    queryFn: () => api.cleanupAnalyze(suggestion.playlist_id),
    enabled: expanded,
    staleTime: 60_000,
  });

  return (
    <li className="overflow-hidden rounded-lg border border-white/10 bg-black/20">
      <details
        className="group"
        onToggle={(event) => setExpanded(event.currentTarget.open)}
      >
        <summary className="cursor-pointer list-none p-4 marker:content-none">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                {suggestion.priority && <PriorityBadge priority={suggestion.priority} />}
                {suggestion.kind && (
                  <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-zinc-400">
                    {suggestion.kind}
                  </span>
                )}
                <span className="text-xs text-zinc-500">{suggestion.playlist_name}</span>
              </div>
              <h4 className="font-medium">{suggestion.title}</h4>
              <p className="mt-1 text-sm text-zinc-400">{suggestion.description}</p>
            </div>
            <span className="shrink-0 pt-1 text-sm text-violet-300 transition group-open:rotate-180">
              ▾
            </span>
          </div>
        </summary>

        <div className="border-t border-white/10 px-4 pb-4 pt-3">
          <p className="mb-4 text-xs text-zinc-500">{suggestion.recommended_action}</p>

          {expanded && analysis.isLoading && (
            <AnalysisSkeleton label="Analyzing playlist…" />
          )}

          {expanded && analysis.isError && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3">
              <p className="mb-2 text-sm text-red-300">Analysis failed for this playlist.</p>
              <button
                type="button"
                onClick={() => analysis.refetch()}
                className="rounded-lg border border-red-500/40 px-3 py-1.5 text-sm text-red-300"
              >
                Retry analysis
              </button>
            </div>
          )}

          {expanded && analysis.data && !analysis.isLoading && (
            <>
              <p className="mb-4 text-sm text-zinc-400">
                {analysis.data.total_tracks} tracks analyzed
              </p>
              <AnalysisActions
                playlistId={suggestion.playlist_id}
                analysis={analysis.data}
                highlightKind={suggestion.kind}
                removePending={removePending}
                splitPending={splitPending}
                onRemove={onRemove}
                onSplit={onSplit}
              />
            </>
          )}
        </div>
      </details>
    </li>
  );
}

function AnalysisActions({
  analysis,
  highlightKind,
  removePending,
  splitPending,
  onRemove,
  onSplit,
}: {
  playlistId: string;
  analysis: CleanupAnalysis;
  highlightKind?: string;
  removePending: boolean;
  splitPending: boolean;
  onRemove: (trackIds: string[]) => void;
  onSplit: (proposals: CleanupCluster[]) => void;
}) {
  const duplicateIds = trackIdsFromIssues(analysis.duplicates);
  const unavailableIds = trackIdsFromIssues(analysis.unavailable);
  const skipIds = trackIdsFromIssues(analysis.skip_heavy);
  const clusters = analysis.clusters;

  const showDuplicates = !highlightKind || highlightKind === "duplicates";
  const showUnavailable = !highlightKind || highlightKind === "unavailable";
  const showSkipHeavy = !highlightKind || highlightKind === "trim";
  const showSplit =
    !highlightKind || highlightKind === "split" || highlightKind === "trim";

  return (
    <div className="space-y-3">
      {showDuplicates && (
        <CleanupSection
          title="Duplicates"
          count={duplicateIds.length}
          highlighted={highlightKind === "duplicates"}
          disabled={removePending}
          onApply={() => onRemove(duplicateIds)}
        />
      )}
      {showUnavailable && (
        <CleanupSection
          title="Unavailable"
          count={unavailableIds.length}
          highlighted={highlightKind === "unavailable"}
          disabled={removePending}
          onApply={() => onRemove(unavailableIds)}
        />
      )}
      {showSkipHeavy && (
        <CleanupSection
          title="Skip-heavy"
          count={skipIds.length}
          highlighted={highlightKind === "trim"}
          disabled={removePending}
          onApply={() => onRemove(skipIds)}
        />
      )}

      {showSplit && clusters.length > 0 && (
        <div
          className={`rounded-xl border p-4 ${
            highlightKind === "split" || highlightKind === "trim"
              ? "border-violet-500/30 bg-violet-500/5"
              : "border-white/10 bg-white/5"
          }`}
        >
          <h3 className="mb-2 font-medium">Split proposals</h3>
          <ul className="mb-4 space-y-1 text-sm text-zinc-400">
            {clusters.map((cluster) => (
              <li key={cluster.cluster_label}>
                {cluster.cluster_label}: {cluster.track_ids.length} tracks
              </li>
            ))}
          </ul>
          <button
            type="button"
            disabled={splitPending}
            onClick={() => onSplit(clusters)}
            className="rounded-lg border border-emerald-500/40 px-4 py-2 text-emerald-300 disabled:opacity-50"
          >
            {splitPending ? "Creating…" : "Create split playlists"}
          </button>
        </div>
      )}

      {duplicateIds.length === 0 &&
        unavailableIds.length === 0 &&
        skipIds.length === 0 &&
        clusters.length === 0 && (
          <p className="text-sm text-zinc-400">No actionable issues found in this analysis.</p>
        )}
    </div>
  );
}

function AnalysisSkeleton({ label }: { label: string }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-500">{label}</p>
      <div className="h-14 animate-pulse rounded-lg bg-white/5" />
      <div className="h-14 animate-pulse rounded-lg bg-white/5" />
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
  highlighted,
  disabled,
  onApply,
}: {
  title: string;
  count: number;
  highlighted?: boolean;
  disabled?: boolean;
  onApply: () => void;
}) {
  return (
    <div
      className={`flex items-center justify-between rounded-xl border p-4 ${
        highlighted ? "border-violet-500/30 bg-violet-500/5" : "border-white/10 bg-white/5"
      }`}
    >
      <div>
        <h3 className="font-medium">{title}</h3>
        <p className="text-sm text-zinc-400">{count} tracks flagged</p>
      </div>
      <button
        type="button"
        disabled={count === 0 || disabled}
        onClick={onApply}
        className="rounded-lg bg-red-500/20 px-4 py-2 text-red-300 disabled:opacity-40"
      >
        Remove
      </button>
    </div>
  );
}
