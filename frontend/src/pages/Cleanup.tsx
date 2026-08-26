import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  type CleanupAiSuggestResult,
  type CleanupAnalysis,
  type CleanupCluster,
  type CleanupIssue,
  type CleanupSuggestion,
  type PlaylistSummary,
  type TrackSummary,
} from "../api/client";
import { UserFacingError } from "../components/UserFacingError";
import { AiAdvisorConfig } from "../components/cleanup/AiAdvisorConfig";
import { DEFAULT_ADVISOR_OPTIONS } from "../components/cleanup/advisorOptions";
import type { CleanupSuggestOptions } from "../api/client";
import { formatDuration } from "../components/playlists/viewMode";
import { useBackgroundActivity } from "../contexts/backgroundActivity";
import { useSpotifyUsage } from "../hooks/useSpotifyUsage";
import { userFacingError } from "../utils/userFacingError";
import { loadAdvisorSession, saveAdvisorSession } from "../utils/pageSessionStorage";

interface AdvisorSessionSnapshot {
  scanOptions: CleanupSuggestOptions;
  aiSuggestions: CleanupAiSuggestResult | null;
  configOpen: boolean;
}

function loadInitialAdvisorState(): AdvisorSessionSnapshot {
  const stored = loadAdvisorSession<Partial<AdvisorSessionSnapshot>>();
  return {
    scanOptions: stored?.scanOptions ?? DEFAULT_ADVISOR_OPTIONS,
    aiSuggestions: stored?.aiSuggestions ?? null,
    configOpen: stored?.configOpen ?? true,
  };
}

function trackIdsFromIssues(issues: { track_ids: string[] }[]): string[] {
  return issues.flatMap((issue) => issue.track_ids);
}

function artistsLabel(track: TrackSummary): string {
  return track.artists.map((artist) => artist.name).join(", ") || "Unknown artist";
}

function tracksMarkedForRemoval(issues: CleanupIssue[]): TrackSummary[] {
  const removeIds = trackIdsFromIssues(issues);
  const byId = new Map<string, TrackSummary>();
  for (const issue of issues) {
    for (const track of issue.tracks ?? []) {
      byId.set(track.id, track);
    }
  }
  return removeIds
    .map((id) => byId.get(id))
    .filter((track): track is TrackSummary => Boolean(track));
}

interface CreatedSplitPlaylist {
  id: string;
  name: string;
  tracks: number;
}

interface PlaylistSuggestionGroupData {
  playlistId: string;
  playlistName: string;
  suggestions: CleanupSuggestion[];
}

const PRIORITY_RANK: Record<string, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

function groupSuggestionsByPlaylist(
  suggestions: CleanupSuggestion[],
): PlaylistSuggestionGroupData[] {
  const groups = new Map<string, PlaylistSuggestionGroupData>();
  for (const suggestion of suggestions) {
    const existing = groups.get(suggestion.playlist_id);
    if (existing) {
      existing.suggestions.push(suggestion);
    } else {
      groups.set(suggestion.playlist_id, {
        playlistId: suggestion.playlist_id,
        playlistName: suggestion.playlist_name,
        suggestions: [suggestion],
      });
    }
  }

  return Array.from(groups.values()).sort((left, right) => {
    const leftRank = Math.min(
      ...left.suggestions.map((item) => PRIORITY_RANK[item.priority ?? "low"] ?? 2),
    );
    const rightRank = Math.min(
      ...right.suggestions.map((item) => PRIORITY_RANK[item.priority ?? "low"] ?? 2),
    );
    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }
    if (right.suggestions.length !== left.suggestions.length) {
      return right.suggestions.length - left.suggestions.length;
    }
    return left.playlistName.localeCompare(right.playlistName);
  });
}

function highestPriority(suggestions: CleanupSuggestion[]): "high" | "medium" | "low" | undefined {
  const sorted = [...suggestions].sort(
    (left, right) =>
      (PRIORITY_RANK[left.priority ?? "low"] ?? 2) - (PRIORITY_RANK[right.priority ?? "low"] ?? 2),
  );
  return sorted[0]?.priority;
}

export function Cleanup() {
  const queryClient = useQueryClient();
  const { setAdvisorActivity } = useBackgroundActivity();
  const initialAdvisorState = useMemo(() => loadInitialAdvisorState(), []);
  const usage = useQuery({
    queryKey: ["playlists"],
    queryFn: api.playlists,
    retry: false,
    staleTime: Infinity,
  });

  const { rateLimited } = useSpotifyUsage();

  const taste = useQuery({
    queryKey: ["taste"],
    queryFn: () => api.taste(false),
    retry: false,
    staleTime: Infinity,
  });
  const playlistItems = useMemo(() => usage.data?.playlists ?? [], [usage.data?.playlists]);
  const [scanOptions, setScanOptions] = useState<CleanupSuggestOptions>(
    initialAdvisorState.scanOptions,
  );
  const [aiSuggestions, setAiSuggestions] = useState<CleanupAiSuggestResult | null>(
    initialAdvisorState.aiSuggestions,
  );
  const [scanStartedAt, setScanStartedAt] = useState<number | null>(null);
  const [scanJobId, setScanJobId] = useState<string | null>(null);
  const [configOpen, setConfigOpen] = useState(initialAdvisorState.configOpen);
  const [scanFailure, setScanFailure] = useState<string | null>(null);
  const [scanCancelled, setScanCancelled] = useState(false);

  const aiSuggest = useMutation({
    mutationFn: (options: CleanupSuggestOptions) => api.cleanupAiSuggestStart(options),
    onMutate: () => {
      setScanStartedAt(Date.now());
      setAiSuggestions(null);
      setScanJobId(null);
      setScanFailure(null);
      setScanCancelled(false);
      setConfigOpen(false);
    },
    onSuccess: (result) => {
      setScanJobId(result.job_id);
    },
    onError: () => {
      setScanStartedAt(null);
      setScanJobId(null);
    },
  });

  const isScanning = (aiSuggest.isPending || Boolean(scanJobId)) && !scanFailure;
  const hasScanSession =
    isScanning || aiSuggestions !== null || scanFailure !== null || scanCancelled;

  useEffect(() => {
    setAdvisorActivity({
      scanning: isScanning,
      hasResults: aiSuggestions !== null,
    });
  }, [aiSuggestions, isScanning, setAdvisorActivity]);

  useEffect(() => {
    saveAdvisorSession({
      scanOptions,
      aiSuggestions,
      configOpen,
    } satisfies AdvisorSessionSnapshot);
  }, [scanOptions, aiSuggestions, configOpen]);

  const cancelScan = async () => {
    const jobId = scanJobId;
    if (jobId) {
      try {
        await api.cleanupAiSuggestCancel(jobId);
      } catch {
        // Still clear local state if cancel request fails (e.g. job already gone).
      }
      void queryClient.cancelQueries({ queryKey: ["cleanup-suggest-job", jobId] });
    }
    aiSuggest.reset();
    setScanJobId(null);
    setScanStartedAt(null);
    setScanFailure(null);
    setScanCancelled(true);
  };

  const clearResults = () => {
    setAiSuggestions(null);
    setScanJobId(null);
    setScanStartedAt(null);
    setScanFailure(null);
    setScanCancelled(false);
    setConfigOpen(true);
    saveAdvisorSession({
      scanOptions,
      aiSuggestions: null,
      configOpen: true,
    });
  };

  const scanJob = useQuery({
    queryKey: ["cleanup-suggest-job", scanJobId],
    queryFn: () => api.cleanupAiSuggestJob(scanJobId!),
    enabled: Boolean(scanJobId),
    retry: (failureCount, error) => {
      if (!(error instanceof Error)) {
        return failureCount < 8;
      }
      const message = error.message.toLowerCase();
      if (message.includes("not found") || message.includes("404")) {
        return false;
      }
      return failureCount < 8;
    },
    retryDelay: (attempt) => Math.min(1000 * (attempt + 1), 5000),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed" || status === "cancelled") {
        return false;
      }
      return 1000;
    },
  });

  useEffect(() => {
    if (scanJob.data?.status === "cancelled") {
      setScanCancelled(true);
      setScanJobId(null);
      setScanStartedAt(null);
      return;
    }

    if (scanJob.data?.status === "completed" && scanJob.data.result) {
      setScanFailure(null);
      setAiSuggestions(scanJob.data.result);
      setScanJobId(null);
      setScanStartedAt(null);
      void queryClient.invalidateQueries({ queryKey: ["playlist-scan-summaries"] });
      return;
    }

    if (scanJob.data?.status === "failed") {
      setScanFailure(
        userFacingError(scanJob.data.error, "Could not generate cleanup suggestions."),
      );
      setScanJobId(null);
      setScanStartedAt(null);
      return;
    }

    if (scanJob.isError && scanJobId) {
      const message = scanJob.error instanceof Error ? scanJob.error.message.toLowerCase() : "";
      if (
        message.includes("not found") ||
        message.includes("404") ||
        message.includes("job not found")
      ) {
        setScanFailure(userFacingError(scanJob.error, "Could not generate cleanup suggestions."));
        setScanJobId(null);
        setScanStartedAt(null);
      }
    }
  }, [scanJob.data, scanJob.error, scanJob.isError, scanJobId, queryClient]);

  const remove = useMutation({
    mutationFn: ({ playlistId, trackIds }: { playlistId: string; trackIds: string[] }) =>
      api.cleanupRemove(playlistId, trackIds),
    onSuccess: async (_, { playlistId }) => {
      await queryClient.invalidateQueries({ queryKey: ["cleanup-analysis", playlistId] });
      await queryClient.invalidateQueries({ queryKey: ["playlists"] });
      await queryClient.invalidateQueries({ queryKey: ["playlist-scan-summaries"] });
    },
  });

  const split = useMutation({
    mutationFn: ({ playlistId, proposals }: { playlistId: string; proposals: CleanupCluster[] }) =>
      api.cleanupSplit(playlistId, proposals),
    onSuccess: async (_, { playlistId }) => {
      await queryClient.invalidateQueries({ queryKey: ["cleanup-analysis", playlistId] });
      await queryClient.invalidateQueries({ queryKey: ["playlists"] });
      await queryClient.invalidateQueries({ queryKey: ["playlist-scan-summaries"] });
    },
  });

  const runDisabled =
    isScanning ||
    rateLimited ||
    (scanOptions.scope === "selected" && scanOptions.playlist_ids.length === 0);

  const playlistById = useMemo(
    () => new Map(playlistItems.map((playlist) => [playlist.id, playlist])),
    [playlistItems],
  );

  const groupedSuggestions = useMemo(
    () => (aiSuggestions ? groupSuggestionsByPlaylist(aiSuggestions.suggestions) : []),
    [aiSuggestions],
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">AI Cleanup Advisor</h2>
        <p className="mt-1 max-w-2xl text-sm text-zinc-400">
          Scans your playlists for duplicates and dead tracks, then uses AI to prioritize cleanups
          based on your taste profile and any instructions you provide.
        </p>
        <p className="mt-2 text-sm text-zinc-500">
          For playlist-by-playlist cleanup, use{" "}
          <Link to="/" className="text-emerald-400 hover:underline">
            Dashboard
          </Link>{" "}
          — scan for issues, open a playlist, and edit tracks there.
        </p>
      </div>

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            {hasScanSession ? (
              <>
                <h3 className="text-lg font-medium text-zinc-100">Advisor scan</h3>
                <p className="mt-1 max-w-xl text-sm text-zinc-500">
                  {isScanning
                    ? "Scan running — expand settings below to tweak options for the next run."
                    : scanCancelled
                      ? "Scan was stopped — adjust settings if needed and run again."
                      : scanFailure
                        ? "The last scan did not finish — adjust settings if needed and run again."
                        : "Review suggestions below, or expand settings to adjust and scan again."}
                </p>
              </>
            ) : (
              <>
                <h3 className="text-lg font-medium text-zinc-100">Set up your scan</h3>
                <p className="mt-1 max-w-xl text-sm text-zinc-500">
                  Most people can pick a quick start and hit Run — expand Fine-tune if you want more
                  control.
                </p>
              </>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {isScanning && (
              <button
                type="button"
                onClick={() => void cancelScan()}
                className="rounded-xl border border-violet-400/40 px-5 py-2.5 text-sm font-semibold text-violet-200 hover:bg-violet-500/10"
              >
                Stop scan
              </button>
            )}
            <button
              type="button"
              disabled={runDisabled}
              onClick={() => aiSuggest.mutate(scanOptions)}
              className="rounded-xl bg-violet-500 px-5 py-2.5 text-sm font-semibold text-black shadow-lg shadow-violet-500/20 disabled:opacity-50"
            >
              {isScanning ? "Scanning…" : hasScanSession ? "Run again" : "Run advisor"}
            </button>
          </div>
        </div>

        {hasScanSession ? (
          <details
            open={configOpen}
            onToggle={(event) => setConfigOpen(event.currentTarget.open)}
            className="rounded-xl border border-white/10 bg-black/20"
          >
            <summary className="cursor-pointer list-none px-4 py-3 marker:content-none">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <span className="font-medium text-zinc-200">Scan settings</span>
                  <p className="mt-0.5 text-xs text-zinc-500">
                    Scope, focus areas, taste profile, schedule, and fine-tune options
                  </p>
                </div>
                <span className="shrink-0 text-sm text-violet-300">{configOpen ? "▴" : "▾"}</span>
              </div>
            </summary>
            <div className="border-t border-white/10 px-4 pb-4 pt-4">
              <AiAdvisorConfig
                options={scanOptions}
                onChange={setScanOptions}
                playlists={playlistItems}
                tasteProfile={taste.data}
                disabled={isScanning}
              />
            </div>
          </details>
        ) : (
          <AiAdvisorConfig
            options={scanOptions}
            onChange={setScanOptions}
            playlists={playlistItems}
            tasteProfile={taste.data}
            disabled={isScanning}
          />
        )}

        {isScanning && (
          <ScanProgress
            startedAt={scanStartedAt ?? Date.now()}
            progress={scanJob.data?.progress}
            onCancel={() => void cancelScan()}
          />
        )}

        {scanCancelled && !isScanning && !scanFailure && (
          <div className="rounded-lg border border-zinc-500/30 bg-zinc-500/10 px-4 py-3 text-sm text-zinc-300">
            Scan cancelled. Run again when you&apos;re ready.
          </div>
        )}

        {aiSuggestions && !isScanning && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-zinc-300">{aiSuggestions.summary}</p>
              <button
                type="button"
                onClick={clearResults}
                className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
              >
                Clear results
              </button>
            </div>
            <p className="text-xs text-zinc-500">
              Scanned {aiSuggestions.scanned_playlists} of {aiSuggestions.total_playlists} playlists
              · grouped by playlist below
            </p>

            {aiSuggestions.suggestions.length === 0 ? (
              <p className="rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-zinc-400">
                No cleanup suggestions right now — your scanned playlists look tidy.
              </p>
            ) : (
              <ul className="space-y-4">
                {groupedSuggestions.map((group) => (
                  <PlaylistSuggestionGroup
                    key={group.playlistId}
                    group={group}
                    playlist={playlistById.get(group.playlistId)}
                    removePending={remove.isPending}
                    splitPending={split.isPending}
                    onRemove={async (trackIds) => {
                      const result = await remove.mutateAsync({
                        playlistId: group.playlistId,
                        trackIds,
                      });
                      return result.removed;
                    }}
                    onSplit={async (proposals) => {
                      const result = await split.mutateAsync({
                        playlistId: group.playlistId,
                        proposals,
                      });
                      return (result.created ?? []) as CreatedSplitPlaylist[];
                    }}
                  />
                ))}
              </ul>
            )}
          </div>
        )}

        {scanFailure && (
          <UserFacingError
            compact
            title="Scan failed"
            error={scanFailure}
            fallback="Could not generate cleanup suggestions."
            onRetry={() => {
              setScanFailure(null);
              aiSuggest.mutate(scanOptions);
            }}
          />
        )}

        {aiSuggest.isError && (
          <UserFacingError
            compact
            title="Could not start scan"
            error={aiSuggest.error}
            onRetry={() => aiSuggest.mutate(scanOptions)}
          />
        )}
      </section>
    </div>
  );
}

function ScanProgress({
  startedAt,
  progress,
  onCancel,
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
  onCancel: () => void;
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
  const percent = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : undefined;

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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-zinc-500">
          Scans run in the background and reuse recent results when possible.
        </p>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-violet-400/30 px-3 py-1.5 text-xs text-violet-200 hover:bg-violet-500/10"
        >
          Stop scan
        </button>
      </div>
    </div>
  );
}

function PlaylistSuggestionGroup({
  group,
  playlist,
  removePending,
  splitPending,
  onRemove,
  onSplit,
}: {
  group: PlaylistSuggestionGroupData;
  playlist?: PlaylistSummary;
  removePending: boolean;
  splitPending: boolean;
  onRemove: (trackIds: string[]) => Promise<number>;
  onSplit: (proposals: CleanupCluster[]) => Promise<CreatedSplitPlaylist[]>;
}) {
  const [activeKind, setActiveKind] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [splitResult, setSplitResult] = useState<CreatedSplitPlaylist[] | null>(null);
  const topPriority = highestPriority(group.suggestions);
  const suggestionKinds = [
    ...new Set(group.suggestions.map((item) => item.kind).filter(Boolean)),
  ] as string[];

  const analysis = useQuery({
    queryKey: ["cleanup-analysis", group.playlistId],
    queryFn: () => api.cleanupAnalyze(group.playlistId),
    enabled: activeKind !== null,
    staleTime: 60_000,
  });

  const toggleKind = (kind: string | undefined) => {
    if (!kind) {
      return;
    }
    setActiveKind((current) => (current === kind ? null : kind));
    setActionMessage(null);
  };

  return (
    <li className="overflow-hidden rounded-xl border border-white/10 bg-black/20">
      <div className="border-b border-white/10 p-4">
        <div className="flex items-start gap-4">
          {playlist?.image_url && (
            <img
              src={playlist.image_url}
              alt=""
              className="h-16 w-16 shrink-0 rounded-lg object-cover"
            />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-xl font-semibold text-zinc-50">{group.playlistName}</h3>
              {topPriority && <PriorityBadge priority={topPriority} />}
            </div>
            <p className="mt-1 text-sm text-zinc-400">
              {group.suggestions.length} cleanup suggestion
              {group.suggestions.length === 1 ? "" : "s"}
              {playlist ? ` · ${playlist.track_count} tracks` : ""}
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {suggestionKinds.map((kind) => (
                <span
                  key={kind}
                  className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-zinc-300"
                >
                  {kind}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4">
          <Link
            to={`/playlists/${group.playlistId}`}
            className="inline-flex rounded-lg border border-emerald-500/40 px-4 py-2 text-sm text-emerald-300 hover:bg-emerald-500/10"
          >
            Open playlist
          </Link>
        </div>
      </div>

      {actionMessage && (
        <div className="border-b border-white/10 px-4 py-3">
          <p className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-200">
            {actionMessage}
          </p>
        </div>
      )}

      {splitResult && splitResult.length > 0 && (
        <div className="border-b border-white/10 px-4 py-3">
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-200">
            <p className="font-medium">Created {splitResult.length} playlists</p>
            <ul className="mt-2 space-y-1 text-xs">
              {splitResult.map((item) => (
                <li key={item.id}>
                  <Link to={`/playlists/${item.id}`} className="text-emerald-300 hover:underline">
                    {item.name}
                  </Link>
                  <span className="text-emerald-200/70"> · {item.tracks} tracks</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <div className="space-y-3 px-4 py-4">
        {group.suggestions.map((suggestion, index) => {
          const kind = suggestion.kind ?? `item-${index}`;
          const isActive = activeKind === suggestion.kind;
          return (
            <div key={`${suggestion.title}-${kind}-${index}`}>
              <SuggestionBanner
                suggestion={suggestion}
                active={isActive}
                onToggle={() => toggleKind(suggestion.kind)}
              />
              {isActive && (
                <div className="mt-2 rounded-b-lg border border-t-0 border-violet-500/30 bg-violet-500/5 px-3 pb-3 pt-2">
                  {analysis.isLoading && (
                    <AnalysisSkeleton label="Loading tracks for this cleanup…" />
                  )}
                  {analysis.isError && (
                    <UserFacingError
                      compact
                      title="Could not load tracks"
                      error={analysis.error}
                      onRetry={() => void analysis.refetch()}
                    />
                  )}
                  {analysis.data && !analysis.isLoading && (
                    <SuggestionActionPanel
                      kind={suggestion.kind}
                      analysis={analysis.data}
                      recommendedAction={suggestion.recommended_action}
                      removePending={removePending}
                      splitPending={splitPending}
                      onRemove={async (trackIds) => {
                        if (trackIds.length === 0) {
                          return;
                        }
                        const removed = await onRemove(trackIds);
                        setActionMessage(
                          `Removed ${removed} track${removed === 1 ? "" : "s"} from ${group.playlistName}.`,
                        );
                        await analysis.refetch();
                        if (trackIds.length > 0 && removed > 0) {
                          setActiveKind(null);
                        }
                      }}
                      onSplit={async (proposals) => {
                        const created = await onSplit(proposals);
                        setSplitResult(created);
                        setActionMessage(
                          `Created ${created.length} split playlist${created.length === 1 ? "" : "s"}.`,
                        );
                        await analysis.refetch();
                      }}
                      onRetryAnalysis={() => void analysis.refetch()}
                    />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </li>
  );
}

function SuggestionBanner({
  suggestion,
  active,
  onToggle,
}: {
  suggestion: CleanupSuggestion;
  active: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`w-full rounded-lg border p-3 text-left transition ${
        active
          ? "border-violet-500/40 bg-violet-500/10 ring-1 ring-violet-500/20"
          : "border-white/10 bg-white/[0.03] hover:border-violet-500/20 hover:bg-white/[0.05]"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            {suggestion.priority && <PriorityBadge priority={suggestion.priority} />}
            {suggestion.kind && (
              <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-zinc-400">
                {suggestion.kind}
              </span>
            )}
          </div>
          <h4 className="font-medium text-zinc-100">{suggestion.title}</h4>
          <p className="mt-1 text-sm text-zinc-400">{suggestion.description}</p>
        </div>
        <span className="shrink-0 pt-1 text-xs text-violet-300">
          {active ? "Hide ▴" : "Review ▾"}
        </span>
      </div>
    </button>
  );
}

function SuggestionActionPanel({
  kind,
  analysis,
  recommendedAction,
  removePending,
  splitPending,
  onRemove,
  onSplit,
  onRetryAnalysis,
}: {
  kind?: string;
  analysis: CleanupAnalysis;
  recommendedAction: string;
  removePending: boolean;
  splitPending: boolean;
  onRemove: (trackIds: string[]) => Promise<void>;
  onSplit: (proposals: CleanupCluster[]) => Promise<void>;
  onRetryAnalysis: () => void;
}) {
  if (kind === "duplicates") {
    const issues = analysis.duplicates;
    const removeIds = trackIdsFromIssues(issues);
    return (
      <DuplicateIssuesPanel
        issues={issues}
        removeIds={removeIds}
        removePending={removePending}
        onRemove={() => void onRemove(removeIds)}
      />
    );
  }

  if (kind === "unavailable") {
    const issues = analysis.unavailable;
    const removeIds = trackIdsFromIssues(issues);
    const tracks = tracksMarkedForRemoval(issues);
    return (
      <RemoveTracksPanel
        title="Unavailable tracks to purge"
        emptyMessage="No unavailable tracks detected in the latest analysis."
        tracks={tracks}
        removeIds={new Set(removeIds)}
        issues={issues}
        removePending={removePending}
        onRemove={() => void onRemove(removeIds)}
      />
    );
  }

  if (kind === "trim") {
    const issues = analysis.skip_heavy;
    const removeIds = trackIdsFromIssues(issues);
    const tracks = tracksMarkedForRemoval(issues);
    return (
      <RemoveTracksPanel
        title="Skip-heavy tracks to remove"
        emptyMessage="No skip-heavy tracks detected in the latest analysis."
        tracks={tracks}
        removeIds={new Set(removeIds)}
        issues={issues}
        removePending={removePending}
        onRemove={() => void onRemove(removeIds)}
      />
    );
  }

  if (kind === "split") {
    return (
      <SplitActionPanel
        analysis={analysis}
        recommendedAction={recommendedAction}
        splitPending={splitPending}
        onSplit={onSplit}
        onRetryAnalysis={onRetryAnalysis}
      />
    );
  }

  if (kind === "merge" || kind === "organize") {
    return (
      <OrganizeActionPanel
        playlistId={analysis.playlist_id}
        recommendedAction={recommendedAction}
      />
    );
  }

  return (
    <PlaylistReviewFallback
      playlistId={analysis.playlist_id}
      recommendedAction={recommendedAction}
      onRetryAnalysis={onRetryAnalysis}
    />
  );
}

function DuplicateIssuesPanel({
  issues,
  removeIds,
  removePending,
  onRemove,
}: {
  issues: CleanupIssue[];
  removeIds: string[];
  removePending: boolean;
  onRemove: () => void;
}) {
  const groups = issues.filter((issue) => (issue.tracks?.length ?? 0) > 0);
  const tracks = tracksMarkedForRemoval(issues);

  if (tracks.length === 0) {
    return (
      <p className="text-sm text-zinc-500">No duplicate tracks detected in the latest analysis.</p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-medium text-zinc-200">
          Duplicate cleanup · {tracks.length} to remove
        </p>
        <button
          type="button"
          disabled={removePending}
          onClick={onRemove}
          className="rounded-lg bg-red-500/20 px-4 py-2 text-sm text-red-300 disabled:opacity-40"
        >
          {removePending
            ? "Removing…"
            : `Remove ${tracks.length} duplicate${tracks.length === 1 ? "" : "s"}`}
        </button>
      </div>

      {groups.length > 0 ? (
        <div className="space-y-3">
          {groups.map((issue, index) => (
            <div
              key={`${issue.kind}-${index}`}
              className="rounded-lg border border-white/10 bg-black/20 p-2"
            >
              <p className="mb-2 px-2 text-xs text-zinc-500">{issue.reason}</p>
              <CleanupTrackList
                tracks={issue.tracks ?? []}
                removeIds={new Set(issue.track_ids)}
                keepLabel="Keep"
              />
            </div>
          ))}
        </div>
      ) : (
        <CleanupTrackList tracks={tracks} removeIds={new Set(removeIds)} />
      )}
    </div>
  );
}

function RemoveTracksPanel({
  title,
  emptyMessage,
  tracks,
  removeIds,
  issues,
  removePending,
  onRemove,
}: {
  title: string;
  emptyMessage: string;
  tracks: TrackSummary[];
  removeIds: Set<string>;
  issues: CleanupIssue[];
  removePending: boolean;
  onRemove: () => void;
}) {
  if (tracks.length === 0) {
    return <p className="text-sm text-zinc-500">{emptyMessage}</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-medium text-zinc-200">
          {title} · {tracks.length}
        </p>
        <button
          type="button"
          disabled={removePending || tracks.length === 0}
          onClick={onRemove}
          className="rounded-lg bg-red-500/20 px-4 py-2 text-sm text-red-300 disabled:opacity-40"
        >
          {removePending
            ? "Removing…"
            : `Remove ${tracks.length} track${tracks.length === 1 ? "" : "s"}`}
        </button>
      </div>

      {issues.some((issue) => issue.tracks && issue.tracks.length > 1) && (
        <div className="space-y-2">
          {issues
            .filter((issue) => issue.tracks && issue.tracks.length > 0)
            .map((issue, index) => (
              <p key={`${issue.kind}-${index}`} className="text-xs text-zinc-500">
                {issue.reason}
              </p>
            ))}
        </div>
      )}

      <CleanupTrackList tracks={tracks} removeIds={removeIds} />
    </div>
  );
}

function CleanupTrackList({
  tracks,
  removeIds,
  keepLabel = "Keep",
}: {
  tracks: TrackSummary[];
  removeIds: Set<string>;
  keepLabel?: string;
}) {
  return (
    <ul className="max-h-72 space-y-2 overflow-y-auto rounded-lg border border-white/10 bg-black/20 p-2">
      {tracks.map((track) => {
        const markedForRemoval = removeIds.has(track.id);
        return (
          <li
            key={track.id}
            className={`flex items-center gap-3 rounded-lg px-2 py-2 ${
              markedForRemoval ? "bg-red-500/10" : "bg-emerald-500/5"
            }`}
          >
            {track.album_image_url ? (
              <img
                src={track.album_image_url}
                alt=""
                className="h-10 w-10 shrink-0 rounded object-cover"
              />
            ) : (
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-white/10 text-xs text-zinc-500">
                ♪
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-zinc-100">{track.name}</p>
              <p className="truncate text-xs text-zinc-500">
                {artistsLabel(track)}
                {track.album ? ` · ${track.album}` : ""}
                {track.duration_ms > 0 ? ` · ${formatDuration(track.duration_ms)}` : ""}
              </p>
            </div>
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide ${
                markedForRemoval
                  ? "bg-red-500/20 text-red-300"
                  : "bg-emerald-500/20 text-emerald-300"
              }`}
            >
              {markedForRemoval ? "Remove" : keepLabel}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function SplitActionPanel({
  analysis,
  recommendedAction,
  splitPending,
  onSplit,
  onRetryAnalysis,
}: {
  analysis: CleanupAnalysis;
  recommendedAction: string;
  splitPending: boolean;
  onSplit: (proposals: CleanupCluster[]) => Promise<void>;
  onRetryAnalysis: () => void;
}) {
  const clusters = analysis.clusters;

  if (clusters.length === 0) {
    return (
      <div className="space-y-3 text-sm text-zinc-400">
        <p>
          Couldn&apos;t auto-generate mood clusters for this playlist — usually missing audio
          features or not enough track variety.
        </p>
        <p className="text-zinc-500">{recommendedAction}</p>
        <div className="flex flex-wrap gap-2">
          <Link
            to={`/playlists/${analysis.playlist_id}`}
            className="rounded-lg border border-emerald-500/40 px-4 py-2 text-emerald-300 hover:bg-emerald-500/10"
          >
            Review tracks on Dashboard
          </Link>
          <button
            type="button"
            onClick={onRetryAnalysis}
            className="rounded-lg border border-white/10 px-4 py-2 text-zinc-300 hover:bg-white/5"
          >
            Retry analysis
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <ul className="space-y-1 text-sm text-zinc-400">
        {clusters.map((cluster) => (
          <li key={cluster.cluster_label}>
            {cluster.cluster_label}: {cluster.track_ids.length} tracks
          </li>
        ))}
      </ul>
      <button
        type="button"
        disabled={splitPending}
        onClick={() => void onSplit(clusters)}
        className="rounded-lg border border-emerald-500/40 px-4 py-2 text-emerald-300 disabled:opacity-50"
      >
        {splitPending ? "Creating…" : "Create split playlists"}
      </button>
    </div>
  );
}

function OrganizeActionPanel({
  playlistId,
  recommendedAction,
}: {
  playlistId: string;
  recommendedAction: string;
}) {
  return (
    <div className="space-y-3 text-sm text-zinc-400">
      <p>This suggestion needs a manual pass — browse tracks and decide what to move or trim.</p>
      <p className="text-zinc-500">{recommendedAction}</p>
      <Link
        to={`/playlists/${playlistId}`}
        className="inline-flex rounded-lg border border-emerald-500/40 px-4 py-2 text-emerald-300 hover:bg-emerald-500/10"
      >
        Open playlist on Dashboard
      </Link>
    </div>
  );
}

function PlaylistReviewFallback({
  playlistId,
  recommendedAction,
  onRetryAnalysis,
}: {
  playlistId: string;
  recommendedAction: string;
  onRetryAnalysis: () => void;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <p className="text-sm text-zinc-400">
        No one-click cleanup is available for this suggestion right now.
      </p>
      <p className="mt-2 text-sm text-zinc-500">{recommendedAction}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          to={`/playlists/${playlistId}`}
          className="rounded-lg border border-emerald-500/40 px-4 py-2 text-emerald-300 hover:bg-emerald-500/10"
        >
          Open playlist on Dashboard
        </Link>
        <button
          type="button"
          onClick={onRetryAnalysis}
          className="rounded-lg border border-white/10 px-4 py-2 text-zinc-300 hover:bg-white/5"
        >
          Retry analysis
        </button>
      </div>
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
