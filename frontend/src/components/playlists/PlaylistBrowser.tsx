import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api,
  type CuratedPlaylistSource,
  type PlaylistsResponse,
  type PlaylistSummary,
} from "../../api/client";
import { CleanupIssueTags } from "./CleanupIssueTags";
import { CuratedSourceBadge } from "./CuratedSourceBadge";
import { PlaylistHoverActions } from "./PlaylistHoverActions";
import { PlaylistMetadataDialog } from "./PlaylistMetadataDialog";
import {
  hasCleanupIssues,
  hasScanData,
  playlistRowHighlightClass,
  type PlaylistScanSummary,
} from "./cleanupInsights";
import { PlaylistOrganizeControls } from "./PlaylistOrganizeControls";
import {
  organizePlaylists,
  usePlaylistOrganizeDefaults,
  usesAccessGrouping,
  type PlaylistAccessGroup,
  type PlaylistSortKey,
} from "./playlistSort";
import { PlaylistTrackPanel, PlaylistTrackPanelPlaceholder } from "./PlaylistTrackPanel";
import { SpotifyUsageBar } from "./SpotifyUsageBar";
import { ViewSwitcher } from "./ViewSwitcher";
import { UserFacingError } from "../UserFacingError";
import { useBackgroundActivity } from "../../contexts/backgroundActivity";
import { useSpotifyUsage } from "../../hooks/useSpotifyUsage";
import {
  loadPlaylistViewMode,
  PlaylistViewMode,
  savePlaylistViewMode,
  type PlaylistViewMode as ViewMode,
} from "./viewMode";

export function PlaylistBrowser() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { usage, rateLimited } = useSpotifyUsage();
  const { setDashboardActivity } = useBackgroundActivity();
  const [viewMode, setViewMode] = useState<ViewMode>(() => loadPlaylistViewMode());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const organizeDefaults = usePlaylistOrganizeDefaults();
  const [sortKey, setSortKey] = useState<PlaylistSortKey>(organizeDefaults.sortKey);
  const [editingPlaylist, setEditingPlaylist] = useState<PlaylistSummary | null>(null);
  const [managingPlaylistId, setManagingPlaylistId] = useState<string | null>(null);
  const [managementError, setManagementError] = useState<unknown>(null);

  const playlists = useQuery({
    queryKey: ["playlists"],
    queryFn: api.playlists,
    retry: false,
    staleTime: Infinity,
  });

  const scanSummaries = useQuery({
    queryKey: ["playlist-scan-summaries"],
    queryFn: api.playlistScanSummaries,
    staleTime: Infinity,
  });

  const [pollingScans, setPollingScans] = useState(false);

  const refreshScans = useMutation({
    mutationFn: () => api.playlistScanSummariesRefresh(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["playlist-scan-summaries"] });
      await queryClient.invalidateQueries({ queryKey: ["playlists"] });
      await queryClient.invalidateQueries({ queryKey: ["spotify-usage"] });
    },
    onError: () => {
      setPollingScans(false);
    },
  });

  const startScanRefresh = useCallback((): boolean => {
    if (rateLimited) {
      return false;
    }
    if (refreshScans.isPending || pollingScans) {
      return false;
    }
    setPollingScans(true);
    refreshScans.mutate(undefined);
    return true;
  }, [rateLimited, pollingScans, refreshScans]);

  const refreshPlaylists = useMutation({
    mutationFn: () => api.playlistsRefresh(),
    onSuccess: async (data) => {
      queryClient.setQueryData(["playlists"], data);
      await queryClient.invalidateQueries({ queryKey: ["spotify-usage"] });
      if (!rateLimited && data.spotify_usage?.state !== "limited") {
        startScanRefresh();
      }
    },
  });

  const updatePlaylistMetadata = useMutation({
    mutationFn: ({
      playlistId,
      payload,
    }: {
      playlistId: string;
      payload: { name: string; description: string; public: boolean };
    }) => api.playlistUpdate(playlistId, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData<PlaylistsResponse>(["playlists"], (current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          playlists: current.playlists.map((playlist) =>
            playlist.id === updated.id ? { ...playlist, ...updated } : playlist,
          ),
        };
      });
      setEditingPlaylist(null);
      setManagementError(null);
      setManagingPlaylistId(null);
    },
    onError: (error) => {
      setManagementError(error);
    },
  });

  const deletePlaylist = useMutation({
    mutationFn: (playlistId: string) => api.playlistDelete(playlistId),
    onSuccess: async (_result, playlistId) => {
      queryClient.setQueryData<PlaylistsResponse>(["playlists"], (current) => {
        if (!current) {
          return current;
        }
        const { [playlistId]: _removed, ...remainingSources } = current.curated_sources ?? {};
        return {
          ...current,
          playlists: current.playlists.filter((playlist) => playlist.id !== playlistId),
          curated_sources: remainingSources,
        };
      });
      if (selectedId === playlistId) {
        setSelectedId(null);
      }
      setManagementError(null);
      setManagingPlaylistId(null);
      await queryClient.invalidateQueries({ queryKey: ["playlist-scan-summaries"] });
      await queryClient.invalidateQueries({ queryKey: ["discover-history"] });
    },
    onError: (error) => {
      setManagementError(error);
    },
  });

  useEffect(() => {
    if (!pollingScans) {
      return;
    }
    const interval = window.setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: ["playlist-scan-summaries"] });
    }, 3000);
    const timeout = window.setTimeout(() => setPollingScans(false), 120_000);
    return () => {
      window.clearInterval(interval);
      window.clearTimeout(timeout);
    };
  }, [pollingScans, queryClient]);

  const handleRefreshScans = () => {
    startScanRefresh();
  };

  const summaries = useMemo(() => scanSummaries.data ?? {}, [scanSummaries.data]);
  const playlistItems = useMemo(() => playlists.data?.playlists ?? [], [playlists.data?.playlists]);
  const ownedPlaylists = playlistItems.filter(
    (playlist) => playlist.can_edit && playlist.track_count > 0,
  );
  const scannedCount = ownedPlaylists.filter((playlist) =>
    hasScanData(summaries[playlist.id]),
  ).length;
  const needsRescan = ownedPlaylists.some((playlist) => !hasScanData(summaries[playlist.id]));
  const isScanning = refreshScans.isPending || pollingScans;
  const hasScanResults =
    ownedPlaylists.length > 0 && scannedCount > 0 && !isScanning && !needsRescan;

  useEffect(() => {
    setDashboardActivity({
      scanning: isScanning,
      hasResults: hasScanResults,
    });
  }, [hasScanResults, isScanning, setDashboardActivity]);

  const curatedSources = useMemo(
    () => playlists.data?.curated_sources ?? {},
    [playlists.data?.curated_sources],
  );

  const playlistGroups = useMemo(
    (): PlaylistAccessGroup[] =>
      organizePlaylists(playlistItems, sortKey, summaries, curatedSources),
    [playlistItems, sortKey, summaries, curatedSources],
  );

  const showGroupHeaders =
    usesAccessGrouping(sortKey) ||
    playlistGroups.some((group) => group.id === "curated" && group.playlists.length > 0);

  const displayedPlaylists = useMemo(
    () => playlistGroups.flatMap((group) => group.playlists),
    [playlistGroups],
  );

  useEffect(() => {
    if (!pollingScans || ownedPlaylists.length === 0) {
      return;
    }
    if (scannedCount >= ownedPlaylists.length) {
      setPollingScans(false);
    }
  }, [pollingScans, ownedPlaylists.length, scannedCount]);

  useEffect(() => {
    if (!playlists.isSuccess || scanSummaries.isLoading) {
      return;
    }
    const items = playlists.data?.playlists ?? [];
    if (items.length === 0) {
      return;
    }
    if (rateLimited) {
      return;
    }
    if (refreshScans.isPending || pollingScans) {
      return;
    }

    if (!needsRescan) {
      return;
    }

    startScanRefresh();
  }, [
    playlists.isSuccess,
    playlists.data?.playlists,
    rateLimited,
    scanSummaries.isLoading,
    needsRescan,
    refreshScans.isPending,
    pollingScans,
    startScanRefresh,
  ]);

  useEffect(() => {
    savePlaylistViewMode(viewMode);
  }, [viewMode]);

  useEffect(() => {
    if (!displayedPlaylists.length) {
      return;
    }
    if (!selectedId || !displayedPlaylists.some((playlist) => playlist.id === selectedId)) {
      setSelectedId(displayedPlaylists[0]?.id ?? null);
    }
  }, [displayedPlaylists, selectedId]);

  const handleViewChange = (mode: ViewMode) => {
    setViewMode(mode);
  };

  const handleColumnSelect = (playlistId: string) => {
    setSelectedId(playlistId);
  };

  const handleOpenPlaylist = (playlistId: string) => {
    if (viewMode === PlaylistViewMode.Column) {
      handleColumnSelect(playlistId);
      return;
    }
    navigate(`/playlists/${playlistId}`);
  };

  const handleEditPlaylist = (playlist: PlaylistSummary) => {
    setManagementError(null);
    setEditingPlaylist(playlist);
  };

  const handleDeletePlaylist = (playlist: PlaylistSummary) => {
    const confirmed = window.confirm(
      `Remove "${playlist.name}" from your Spotify library? This cannot be undone.`,
    );
    if (!confirmed) {
      return;
    }
    setManagementError(null);
    setManagingPlaylistId(playlist.id);
    deletePlaylist.mutate(playlist.id);
  };

  const playlistManagementBusy =
    updatePlaylistMetadata.isPending || deletePlaylist.isPending || rateLimited;

  if (playlists.isLoading) {
    return <p className="text-zinc-400">Loading saved playlists…</p>;
  }

  if (playlists.isError) {
    return (
      <UserFacingError
        title="Couldn't load saved playlists"
        error={playlists.error}
        onRetry={() => void queryClient.invalidateQueries({ queryKey: ["playlists"] })}
      />
    );
  }

  const playlistData = playlists.data;
  const items = playlistItems;
  const issueCount = items.filter((p) => hasCleanupIssues(summaries[p.id])).length;

  let scanStatusLine = "";
  if (ownedPlaylists.length > 0) {
    if (isScanning) {
      scanStatusLine = `Scanning for issues… ${scannedCount} of ${ownedPlaylists.length} playlists done`;
    } else if (scannedCount === 0) {
      scanStatusLine = "No scan results yet — click Scan for issues (may take a few minutes)";
    } else if (scannedCount < ownedPlaylists.length) {
      scanStatusLine = `${scannedCount} of ${ownedPlaylists.length} playlists scanned · ${issueCount} with issues`;
    } else {
      scanStatusLine = `${issueCount} playlist${issueCount === 1 ? "" : "s"} with cleanup issues · ${scannedCount} scanned`;
    }
  } else if (items.length > 0) {
    scanStatusLine = "Reload playlists to enable issue scanning";
  }

  return (
    <div className="space-y-4">
      <SpotifyUsageBar
        usage={usage}
        lastFetchedAt={playlistData?.last_fetched_at}
        refreshing={refreshPlaylists.isPending}
        onRefresh={() => refreshPlaylists.mutate()}
      />

      {playlistData?.cache_message && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm text-amber-200">
          {playlistData.cache_message}
        </div>
      )}

      {refreshPlaylists.isError && (
        <UserFacingError
          compact
          title="Refresh failed"
          error={refreshPlaylists.error}
          onRetry={() => refreshPlaylists.mutate()}
        />
      )}

      {refreshScans.isError && (
        <UserFacingError
          compact
          title="Scan failed"
          error={refreshScans.error}
          onRetry={handleRefreshScans}
        />
      )}

      {managementError != null && !editingPlaylist && (
        <UserFacingError
          compact
          title="Playlist action failed"
          error={managementError}
          onRetry={() => setManagementError(null)}
          retryLabel="Dismiss"
        />
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Your Playlists</h2>
          {scanStatusLine && <p className="mt-1 text-sm text-zinc-500">{scanStatusLine}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={refreshScans.isPending || pollingScans || rateLimited}
            onClick={handleRefreshScans}
            className="rounded-lg border border-white/10 px-3 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-50"
          >
            {refreshScans.isPending || pollingScans ? "Scanning…" : "Scan for issues"}
          </button>
          <PlaylistOrganizeControls sortKey={sortKey} onSortChange={setSortKey} />
          <ViewSwitcher value={viewMode} onChange={handleViewChange} />
        </div>
      </div>

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 px-6 py-12 text-center">
          <p className="text-zinc-400">No playlists loaded yet.</p>
          <p className="mt-1 text-sm text-zinc-500">
            Click <strong className="text-zinc-300">Refresh playlists</strong> above to fetch from
            Spotify.
          </p>
        </div>
      ) : viewMode === PlaylistViewMode.Column ? (
        <ColumnLayout
          groups={playlistGroups}
          showGroupHeaders={showGroupHeaders}
          selectedId={selectedId}
          summaries={summaries}
          curatedSources={curatedSources}
          managingPlaylistId={managingPlaylistId}
          managementDisabled={playlistManagementBusy}
          onEdit={handleEditPlaylist}
          onDelete={handleDeletePlaylist}
          onSelect={handleColumnSelect}
        />
      ) : viewMode === PlaylistViewMode.Tile ? (
        <GroupedTileView
          groups={playlistGroups}
          showGroupHeaders={showGroupHeaders}
          summaries={summaries}
          curatedSources={curatedSources}
          managingPlaylistId={managingPlaylistId}
          managementDisabled={playlistManagementBusy}
          onEdit={handleEditPlaylist}
          onDelete={handleDeletePlaylist}
          onOpen={handleOpenPlaylist}
        />
      ) : (
        <GroupedListView
          groups={playlistGroups}
          showGroupHeaders={showGroupHeaders}
          summaries={summaries}
          curatedSources={curatedSources}
          managingPlaylistId={managingPlaylistId}
          managementDisabled={playlistManagementBusy}
          onEdit={handleEditPlaylist}
          onDelete={handleDeletePlaylist}
          onOpen={handleOpenPlaylist}
        />
      )}

      {editingPlaylist && (
        <PlaylistMetadataDialog
          playlist={editingPlaylist}
          saving={updatePlaylistMetadata.isPending}
          error={managementError}
          onClose={() => {
            if (updatePlaylistMetadata.isPending) {
              return;
            }
            setEditingPlaylist(null);
            setManagementError(null);
          }}
          onSave={(payload) => {
            setManagingPlaylistId(editingPlaylist.id);
            updatePlaylistMetadata.mutate({
              playlistId: editingPlaylist.id,
              payload,
            });
          }}
        />
      )}
    </div>
  );
}

function PlaylistGroupHeader({
  label,
  description,
  count,
  compact = false,
}: {
  label: string;
  description: string;
  count: number;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "px-4 py-3" : "mb-3"}>
      <div className="flex items-baseline gap-2">
        <h3 className={`font-medium text-zinc-200 ${compact ? "text-sm" : "text-base"}`}>
          {label}
        </h3>
        <span className="text-xs text-zinc-500">{count}</span>
      </div>
      {description && (
        <p className={`mt-0.5 text-zinc-500 ${compact ? "text-[11px]" : "text-xs"}`}>
          {description}
        </p>
      )}
    </div>
  );
}

function ColumnLayout({
  groups,
  showGroupHeaders,
  selectedId,
  summaries,
  curatedSources,
  managingPlaylistId,
  managementDisabled,
  onEdit,
  onDelete,
  onSelect,
}: {
  groups: PlaylistAccessGroup[];
  showGroupHeaders: boolean;
  selectedId: string | null;
  summaries: Record<string, PlaylistScanSummary>;
  curatedSources: Record<string, CuratedPlaylistSource>;
  managingPlaylistId: string | null;
  managementDisabled: boolean;
  onEdit: (playlist: PlaylistSummary) => void;
  onDelete: (playlist: PlaylistSummary) => void;
  onSelect: (id: string) => void;
}) {
  const selectedSummary = selectedId ? summaries[selectedId] : undefined;
  const shouldAnalyze = hasCleanupIssues(selectedSummary);

  const cleanup = useQuery({
    queryKey: ["cleanup-analysis", selectedId ?? ""],
    queryFn: () => api.cleanupAnalyze(selectedId!),
    enabled: Boolean(selectedId && shouldAnalyze),
    staleTime: 60_000,
  });

  return (
    <div className="flex h-[min(70vh,720px)] overflow-hidden rounded-xl border border-white/10 bg-black/20">
      <div className="w-80 shrink-0 overflow-y-auto border-r border-white/10">
        <GroupedListView
          groups={groups}
          showGroupHeaders={showGroupHeaders}
          summaries={summaries}
          curatedSources={curatedSources}
          managingPlaylistId={managingPlaylistId}
          managementDisabled={managementDisabled}
          onEdit={onEdit}
          onDelete={onDelete}
          selectedId={selectedId}
          onSelect={onSelect}
          embedded
        />
      </div>
      <div className="min-w-0 flex-1">
        {selectedId ? (
          <PlaylistTrackPanel
            playlistId={selectedId}
            compact
            cleanupAnalysis={cleanup.data}
            cleanupLoading={cleanup.isLoading}
          />
        ) : (
          <PlaylistTrackPanelPlaceholder />
        )}
      </div>
    </div>
  );
}

function GroupedTileView({
  groups,
  showGroupHeaders,
  summaries,
  curatedSources,
  managingPlaylistId,
  managementDisabled,
  onEdit,
  onDelete,
  onOpen,
}: {
  groups: PlaylistAccessGroup[];
  showGroupHeaders: boolean;
  summaries: Record<string, PlaylistScanSummary>;
  curatedSources: Record<string, CuratedPlaylistSource>;
  managingPlaylistId: string | null;
  managementDisabled: boolean;
  onEdit: (playlist: PlaylistSummary) => void;
  onDelete: (playlist: PlaylistSummary) => void;
  onOpen: (id: string) => void;
}) {
  return (
    <div className="space-y-8">
      {groups.map((group) => (
        <section key={group.id}>
          {showGroupHeaders && group.label && (
            <PlaylistGroupHeader
              label={group.label}
              description={group.description}
              count={group.playlists.length}
            />
          )}
          <TileView
            playlists={group.playlists}
            summaries={summaries}
            curatedSources={curatedSources}
            managingPlaylistId={managingPlaylistId}
            managementDisabled={managementDisabled}
            onEdit={onEdit}
            onDelete={onDelete}
            onOpen={onOpen}
          />
        </section>
      ))}
    </div>
  );
}

function GroupedListView({
  groups,
  showGroupHeaders,
  summaries,
  curatedSources,
  managingPlaylistId,
  managementDisabled,
  onEdit,
  onDelete,
  selectedId,
  onSelect,
  onOpen,
  embedded = false,
}: {
  groups: PlaylistAccessGroup[];
  showGroupHeaders: boolean;
  summaries: Record<string, PlaylistScanSummary>;
  curatedSources: Record<string, CuratedPlaylistSource>;
  managingPlaylistId: string | null;
  managementDisabled: boolean;
  onEdit: (playlist: PlaylistSummary) => void;
  onDelete: (playlist: PlaylistSummary) => void;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  onOpen?: (id: string) => void;
  embedded?: boolean;
}) {
  return (
    <div className={embedded ? "" : "space-y-8"}>
      {groups.map((group, groupIndex) => (
        <section key={group.id}>
          {showGroupHeaders && group.label && (
            <PlaylistGroupHeader
              label={group.label}
              description={group.description}
              count={group.playlists.length}
              compact={embedded}
            />
          )}
          <ListView
            playlists={group.playlists}
            summaries={summaries}
            curatedSources={curatedSources}
            managingPlaylistId={managingPlaylistId}
            managementDisabled={managementDisabled}
            onEdit={onEdit}
            onDelete={onDelete}
            selectedId={selectedId}
            onSelect={onSelect}
            onOpen={onOpen}
            embedded={embedded}
            grouped={showGroupHeaders && groupIndex > 0}
          />
        </section>
      ))}
    </div>
  );
}

function TileView({
  playlists,
  summaries,
  curatedSources,
  managingPlaylistId,
  managementDisabled,
  onEdit,
  onDelete,
  onOpen,
}: {
  playlists: PlaylistSummary[];
  summaries: Record<string, PlaylistScanSummary>;
  curatedSources: Record<string, CuratedPlaylistSource>;
  managingPlaylistId: string | null;
  managementDisabled: boolean;
  onEdit: (playlist: PlaylistSummary) => void;
  onDelete: (playlist: PlaylistSummary) => void;
  onOpen: (id: string) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {playlists.map((playlist) => {
        const summary = summaries[playlist.id];
        const hasIssues = hasCleanupIssues(summary);
        const curatedSource = curatedSources[playlist.id];
        const isManaging = managingPlaylistId === playlist.id;
        return (
          <div
            key={playlist.id}
            className={`group relative rounded-xl border transition hover:bg-white/5 ${
              hasIssues ? "border-amber-500/30 bg-amber-500/5" : "border-white/10 bg-white/5"
            } ${isManaging ? "opacity-60" : ""}`}
          >
            <button
              type="button"
              onClick={() => onOpen(playlist.id)}
              className="w-full p-4 text-left"
            >
              {playlist.image_url ? (
                <img
                  src={playlist.image_url}
                  alt=""
                  className="mb-3 h-32 w-full rounded-lg object-cover"
                />
              ) : (
                <div className="mb-3 flex h-32 w-full items-center justify-center rounded-lg bg-zinc-800 text-zinc-600">
                  ♫
                </div>
              )}
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <h3 className="font-medium">{playlist.name}</h3>
                {curatedSource && <CuratedSourceBadge source={curatedSource} size="xs" />}
              </div>
              <p className="mb-2 text-sm text-zinc-400">
                {playlist.track_count} tracks · {playlist.owner}
              </p>
              <CleanupIssueTags
                summary={summary}
                canScan={playlist.can_edit && playlist.track_count > 0}
                viewOnly={!playlist.can_edit && playlist.track_count > 0}
              />
            </button>
            {playlist.can_edit && (
              <div className="pointer-events-none absolute right-2 top-2 opacity-0 transition group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100">
                <PlaylistHoverActions
                  disabled={managementDisabled || isManaging}
                  onEdit={() => onEdit(playlist)}
                  onDelete={() => onDelete(playlist)}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ListView({
  playlists,
  summaries,
  curatedSources,
  managingPlaylistId,
  managementDisabled,
  onEdit,
  onDelete,
  selectedId,
  onSelect,
  onOpen,
  embedded = false,
  grouped = false,
}: {
  playlists: PlaylistSummary[];
  summaries: Record<string, PlaylistScanSummary>;
  curatedSources: Record<string, CuratedPlaylistSource>;
  managingPlaylistId: string | null;
  managementDisabled: boolean;
  onEdit: (playlist: PlaylistSummary) => void;
  onDelete: (playlist: PlaylistSummary) => void;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  onOpen?: (id: string) => void;
  embedded?: boolean;
  grouped?: boolean;
}) {
  return (
    <ul
      className={
        embedded
          ? grouped
            ? "border-t border-white/10"
            : ""
          : grouped
            ? "overflow-hidden rounded-xl border border-white/10"
            : "overflow-hidden rounded-xl border border-white/10"
      }
    >
      {playlists.map((playlist) => {
        const summary = summaries[playlist.id];
        const highlight = playlistRowHighlightClass(summary);
        const isSelected = selectedId === playlist.id;
        const curatedSource = curatedSources[playlist.id];
        const isManaging = managingPlaylistId === playlist.id;
        const showActions = playlist.can_edit;

        const content = (
          <>
            {playlist.image_url ? (
              <img src={playlist.image_url} alt="" className="h-10 w-10 rounded object-cover" />
            ) : (
              <div className="flex h-10 w-10 items-center justify-center rounded bg-zinc-800 text-zinc-600">
                ♫
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate font-medium">{playlist.name}</p>
                {curatedSource && <CuratedSourceBadge source={curatedSource} size="xs" />}
              </div>
              <p className="truncate text-sm text-zinc-400">
                {playlist.track_count} tracks · {playlist.owner}
              </p>
              <div className="mt-1.5">
                <CleanupIssueTags
                  summary={summary}
                  canScan={playlist.can_edit && playlist.track_count > 0}
                  viewOnly={!playlist.can_edit && playlist.track_count > 0}
                  size="xs"
                />
              </div>
            </div>
            {showActions ? (
              <div className="flex shrink-0 items-center gap-2">
                <div className="opacity-0 transition group-hover:opacity-100 group-focus-within:opacity-100">
                  <PlaylistHoverActions
                    compact
                    disabled={managementDisabled || isManaging}
                    onEdit={() => onEdit(playlist)}
                    onDelete={() => onDelete(playlist)}
                  />
                </div>
                {isSelected && embedded ? (
                  <span className="text-emerald-400" aria-hidden>
                    ›
                  </span>
                ) : (
                  !embedded && (
                    <span className="text-zinc-500 group-hover:hidden" aria-hidden>
                      ›
                    </span>
                  )
                )}
              </div>
            ) : (
              <>
                {isSelected && embedded && (
                  <span className="text-emerald-400" aria-hidden>
                    ›
                  </span>
                )}
                {!embedded && (
                  <span className="text-zinc-500" aria-hidden>
                    ›
                  </span>
                )}
              </>
            )}
          </>
        );

        const className = `group flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-white/5 ${highlight} ${
          isSelected ? "bg-emerald-500/10" : ""
        } ${isManaging ? "opacity-60" : ""} border-b border-white/5 last:border-b-0`;

        if (onSelect) {
          return (
            <li key={playlist.id}>
              <button type="button" onClick={() => onSelect(playlist.id)} className={className}>
                {content}
              </button>
            </li>
          );
        }

        return (
          <li key={playlist.id}>
            <button type="button" onClick={() => onOpen?.(playlist.id)} className={className}>
              {content}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
