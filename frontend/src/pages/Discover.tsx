import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type DiscoverHistoryItem,
  type DiscoverProposal,
  type DiscoverRationale,
} from "../api/client";
import { DiscoverHistorySidebar } from "../components/discover/DiscoverHistorySidebar";
import {
  DiscoverProposalPanel,
  DiscoverProposalPlaceholder,
} from "../components/discover/DiscoverProposalPanel";
import {
  DiscoverRemoveDialog,
  type DiscoverRemoveChoice,
} from "../components/discover/DiscoverRemoveDialog";
import { UserFacingError } from "../components/UserFacingError";
import { useBackgroundActivity } from "../contexts/backgroundActivity";
import { useCancellableMutation } from "../hooks/useCancellableMutation";
import { useSpotifyUsage } from "../hooks/useSpotifyUsage";
import { userFacingError } from "../utils/userFacingError";
import {
  clearDiscoverSession,
  loadDiscoverSession,
  saveDiscoverSession,
} from "../utils/pageSessionStorage";

interface DiscoverSessionSnapshot {
  selectedRunId: string | null;
}

function emptyRationale(): DiscoverRationale {
  return {
    summary: "",
    core_genres: [],
    spotlight_artists: [],
    discovery_picks: [],
    energy_notes: "",
    flow_strategy: "",
    excluded: [],
  };
}

function normalizeProposal(proposal: DiscoverProposal): DiscoverProposal {
  return {
    ...proposal,
    rationale: {
      ...emptyRationale(),
      ...proposal.rationale,
      summary: proposal.rationale?.summary || proposal.reasoning || "",
    },
    tracks: proposal.tracks ?? [],
    track_uris: proposal.track_uris ?? proposal.tracks?.map((track) => track.uri) ?? [],
    track_count: proposal.tracks?.length ?? proposal.track_count ?? 0,
  };
}

function loadInitialDiscoverState(): DiscoverSessionSnapshot {
  const stored = loadDiscoverSession<DiscoverSessionSnapshot & { activeRun?: DiscoverProposal }>();
  return {
    selectedRunId: stored?.selectedRunId ?? stored?.activeRun?.run_id ?? null,
  };
}

export function Discover() {
  const queryClient = useQueryClient();
  const { rateLimited } = useSpotifyUsage();
  const { setDiscoverActivity } = useBackgroundActivity();
  const initialState = useMemo(() => loadInitialDiscoverState(), []);
  const [activeRun, setActiveRun] = useState<DiscoverProposal | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(initialState.selectedRunId);
  const [tracks, setTracks] = useState<DiscoverProposal["tracks"]>([]);
  const initialFetchDone = useRef(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [loadingRunId, setLoadingRunId] = useState<string | null>(null);
  const [removingRunId, setRemovingRunId] = useState<string | null>(null);
  const [removeTarget, setRemoveTarget] = useState<DiscoverHistoryItem | null>(null);
  const [removeError, setRemoveError] = useState<unknown>(null);

  const history = useQuery({
    queryKey: ["discover-history"],
    queryFn: api.discoverHistory,
  });

  const generate = useCancellableMutation(
    (_variables, signal) => api.discoverGenerate({ signal }),
    {
      onSuccess: (data) => {
        const proposal = normalizeProposal(data);
        setActiveRun(proposal);
        setSelectedRunId(proposal.run_id);
        setTracks(proposal.tracks);
        setSaveError(null);
        void history.refetch();
      },
    },
  );

  const save = useCancellableMutation(
    ({ runId, trackUris }: { runId: string; trackUris: string[] }, signal) =>
      api.discoverSave(runId, trackUris, { signal }),
    {
      onSuccess: (data) => {
        const proposal = normalizeProposal(data);
        setActiveRun(proposal);
        setSelectedRunId(proposal.run_id);
        setTracks(proposal.tracks);
        setSaveError(null);
        void history.refetch();
        void queryClient.invalidateQueries({ queryKey: ["playlists"] });
      },
      onError: (error) => {
        setSaveError(error instanceof Error ? error.message : "Could not save playlist.");
      },
    },
  );

  const displayedRun = generate.data
    ? normalizeProposal(generate.data)
    : activeRun
      ? normalizeProposal({ ...activeRun, tracks })
      : null;
  const isGenerating = generate.isPending;
  const isSaving = save.isPending;
  const discoverBusy = isGenerating || isSaving;
  const showColumnLayout = Boolean(
    (history.data && history.data.length > 0) || displayedRun || isGenerating,
  );

  const cancelGenerate = () => {
    generate.cancel();
    setDiscoverActivity({
      busy: false,
      hasResults: displayedRun !== null,
    });
  };

  useEffect(() => {
    setDiscoverActivity({
      busy: discoverBusy,
      hasResults: displayedRun !== null && !discoverBusy,
    });
  }, [displayedRun, discoverBusy, setDiscoverActivity]);

  useEffect(() => {
    saveDiscoverSession({ selectedRunId });
  }, [selectedRunId]);

  const openHistoryRun = useCallback(
    async (runId: string) => {
      setSelectedRunId(runId);
      setLoadingRunId(runId);
      setHistoryError(null);
      setSaveError(null);
      try {
        const proposal = normalizeProposal(await api.discoverRun(runId));
        setActiveRun(proposal);
        setTracks(proposal.tracks);
        generate.reset();
        save.reset();
      } catch (error) {
        setHistoryError(userFacingError(error, "Could not load discovery run."));
      } finally {
        setLoadingRunId(null);
      }
    },
    [generate, save],
  );

  useEffect(() => {
    if (initialFetchDone.current || !selectedRunId || history.isLoading) {
      return;
    }
    if (!history.data?.some((run) => run.run_id === selectedRunId)) {
      return;
    }
    initialFetchDone.current = true;
    void openHistoryRun(selectedRunId);
  }, [history.data, history.isLoading, openHistoryRun, selectedRunId]);

  const clearResult = () => {
    setActiveRun(null);
    setSelectedRunId(null);
    setTracks([]);
    setSaveError(null);
    generate.reset();
    save.reset();
    clearDiscoverSession();
  };

  const removeTrack = (trackId: string) => {
    setTracks((current) => current.filter((track) => track.id !== trackId));
  };

  const removeHistoryRun = async (run: DiscoverHistoryItem, choice: DiscoverRemoveChoice) => {
    setRemovingRunId(run.run_id);
    setRemoveError(null);
    setHistoryError(null);
    try {
      await api.discoverRemove(run.run_id, {
        remove_history: choice.removeHistory,
        delete_playlist: choice.deletePlaylist,
      });
      if (activeRun?.run_id === run.run_id || displayedRun?.run_id === run.run_id) {
        clearResult();
      } else if (selectedRunId === run.run_id) {
        setSelectedRunId(null);
      }
      setRemoveTarget(null);
      await history.refetch();
      if (choice.deletePlaylist) {
        await queryClient.invalidateQueries({ queryKey: ["playlists"] });
        await queryClient.invalidateQueries({ queryKey: ["playlist-scan-summaries"] });
      }
    } catch (error) {
      setRemoveError(error);
      setHistoryError(userFacingError(error, "Could not remove discovery run."));
    } finally {
      setRemovingRunId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Discover</h2>
          <p className="text-zinc-400">
            Generate a playlist proposal from your taste — review it, then save to Spotify when
            you&apos;re happy.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {isGenerating && (
            <button
              type="button"
              onClick={cancelGenerate}
              className="rounded-lg border border-sky-400/40 px-4 py-2 text-sm text-sky-200 hover:bg-sky-500/10"
            >
              Cancel
            </button>
          )}
          {displayedRun && (
            <button
              type="button"
              onClick={clearResult}
              disabled={isGenerating || isSaving}
              className="rounded-lg border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-60"
            >
              Clear
            </button>
          )}
          <button
            type="button"
            onClick={() => generate.mutate()}
            disabled={isGenerating || isSaving || rateLimited}
            className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black disabled:opacity-50"
          >
            {isGenerating ? "Generating…" : displayedRun ? "Generate again" : "Generate now"}
          </button>
        </div>
      </div>

      {isGenerating && (
        <div className="rounded-xl border border-sky-500/20 bg-sky-500/5 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm text-sky-200">Building your discovery proposal…</p>
              <p className="mt-1 text-xs text-zinc-500">
                Tracks are selected from Spotify recommendations — nothing is saved until you
                approve.
              </p>
            </div>
            <button
              type="button"
              onClick={cancelGenerate}
              className="rounded-lg border border-sky-400/30 px-3 py-1.5 text-xs text-sky-200 hover:bg-sky-500/10"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {generate.isError && (
        <UserFacingError
          compact
          title="Generation failed"
          error={generate.error}
          onRetry={() => generate.mutate()}
        />
      )}

      {historyError && (
        <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4">
          <p className="mb-1 text-sm font-medium text-red-200">History action failed</p>
          <p className="text-sm text-red-300/90">{historyError}</p>
        </div>
      )}

      {showColumnLayout && (
        <div className="flex h-[min(70vh,720px)] overflow-hidden rounded-xl border border-white/10 bg-black/20">
          <div className="w-80 shrink-0 overflow-hidden border-r border-white/10">
            {history.data && history.data.length > 0 ? (
              <DiscoverHistorySidebar
                runs={history.data}
                selectedRunId={selectedRunId}
                loadingRunId={loadingRunId}
                removingRunId={removingRunId}
                onSelect={(runId) => void openHistoryRun(runId)}
                onRemove={(run) => {
                  setRemoveError(null);
                  setRemoveTarget(run);
                }}
              />
            ) : (
              <div className="flex h-full items-center justify-center p-6 text-center text-sm text-zinc-500">
                Recent runs will appear here after your first generation.
              </div>
            )}
          </div>
          <div className="min-w-0 flex-1">
            {displayedRun && selectedRunId === displayedRun.run_id ? (
              <DiscoverProposalPanel
                proposal={displayedRun}
                tracks={tracks}
                loading={loadingRunId === displayedRun.run_id}
                isSaving={isSaving}
                saveError={saveError}
                rateLimited={rateLimited}
                onRemoveTrack={removeTrack}
                onSave={() =>
                  save.mutate({
                    runId: displayedRun.run_id,
                    trackUris: tracks.map((track) => track.uri),
                  })
                }
              />
            ) : (
              <DiscoverProposalPlaceholder />
            )}
          </div>
        </div>
      )}

      {removeTarget && (
        <DiscoverRemoveDialog
          run={removeTarget}
          removing={removingRunId === removeTarget.run_id}
          error={removeError}
          onClose={() => {
            if (removingRunId === removeTarget.run_id) {
              return;
            }
            setRemoveTarget(null);
            setRemoveError(null);
          }}
          onConfirm={(choice) => void removeHistoryRun(removeTarget, choice)}
        />
      )}
    </div>
  );
}
