import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type PlaylistSummary } from "../../api/client";
import { PlaylistTrackPanel, PlaylistTrackPanelPlaceholder } from "./PlaylistTrackPanel";
import { ViewSwitcher } from "./ViewSwitcher";
import {
  loadPlaylistViewMode,
  PlaylistViewMode,
  savePlaylistViewMode,
  type PlaylistViewMode as ViewMode,
} from "./viewMode";

export function PlaylistBrowser() {
  const [viewMode, setViewMode] = useState<ViewMode>(() => loadPlaylistViewMode());
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const playlists = useQuery({
    queryKey: ["playlists"],
    queryFn: api.playlists,
  });

  useEffect(() => {
    savePlaylistViewMode(viewMode);
  }, [viewMode]);

  useEffect(() => {
    if (!selectedId && playlists.data?.length) {
      setSelectedId(playlists.data[0].id);
    }
  }, [playlists.data, selectedId]);

  const handleViewChange = (mode: ViewMode) => {
    setViewMode(mode);
  };

  const handleSelect = (playlistId: string) => {
    setSelectedId(playlistId);
  };

  if (playlists.isLoading) {
    return <p className="text-zinc-400">Loading playlists…</p>;
  }

  if (playlists.isError) {
    return (
      <p className="text-red-400">
        Failed to load playlists. Try refreshing or reconnecting Spotify.
      </p>
    );
  }

  const items = playlists.data ?? [];
  if (items.length === 0) {
    return <p className="text-zinc-400">No playlists found.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold">Your Playlists</h2>
        <ViewSwitcher value={viewMode} onChange={handleViewChange} />
      </div>

      {viewMode === PlaylistViewMode.Column ? (
        <ColumnLayout
          playlists={items}
          selectedId={selectedId}
          onSelect={handleSelect}
        />
      ) : (
        <>
          {viewMode === PlaylistViewMode.Tile ? (
            <TileView
              playlists={items}
              selectedId={selectedId}
              onSelect={handleSelect}
            />
          ) : (
            <ListView
              playlists={items}
              selectedId={selectedId}
              onSelect={handleSelect}
            />
          )}
          {selectedId && (
            <div className="overflow-hidden rounded-xl border border-white/10 bg-black/20">
              <PlaylistTrackPanel playlistId={selectedId} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ColumnLayout({
  playlists,
  selectedId,
  onSelect,
}: {
  playlists: PlaylistSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex h-[min(70vh,720px)] overflow-hidden rounded-xl border border-white/10 bg-black/20">
      <div className="w-72 shrink-0 overflow-y-auto border-r border-white/10">
        <ListView
          playlists={playlists}
          selectedId={selectedId}
          onSelect={onSelect}
          embedded
        />
      </div>
      <div className="min-w-0 flex-1">
        {selectedId ? (
          <PlaylistTrackPanel playlistId={selectedId} compact />
        ) : (
          <PlaylistTrackPanelPlaceholder />
        )}
      </div>
    </div>
  );
}

function TileView({
  playlists,
  selectedId,
  onSelect,
}: {
  playlists: PlaylistSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {playlists.map((playlist) => (
        <button
          key={playlist.id}
          type="button"
          onClick={() => onSelect(playlist.id)}
          className={`rounded-xl border p-4 text-left transition hover:bg-white/5 ${
            selectedId === playlist.id
              ? "border-emerald-500/40 bg-emerald-500/5"
              : "border-white/10 bg-white/5"
          }`}
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
          <h3 className="font-medium">{playlist.name}</h3>
          <p className="text-sm text-zinc-400">
            {playlist.track_count} tracks · {playlist.owner}
          </p>
        </button>
      ))}
    </div>
  );
}

function ListView({
  playlists,
  selectedId,
  onSelect,
  embedded = false,
}: {
  playlists: PlaylistSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  embedded?: boolean;
}) {
  return (
    <ul className={embedded ? "" : "overflow-hidden rounded-xl border border-white/10"}>
      {playlists.map((playlist) => (
        <li key={playlist.id}>
          <button
            type="button"
            onClick={() => onSelect(playlist.id)}
            className={`flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-white/5 ${
              selectedId === playlist.id ? "bg-emerald-500/10" : ""
            } ${embedded ? "border-b border-white/5" : "border-b border-white/5 last:border-b-0"}`}
          >
            {playlist.image_url ? (
              <img
                src={playlist.image_url}
                alt=""
                className="h-10 w-10 rounded object-cover"
              />
            ) : (
              <div className="flex h-10 w-10 items-center justify-center rounded bg-zinc-800 text-zinc-600">
                ♫
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{playlist.name}</p>
              <p className="truncate text-sm text-zinc-400">
                {playlist.track_count} tracks · {playlist.owner}
              </p>
            </div>
            {selectedId === playlist.id && (
              <span className="text-emerald-400" aria-hidden>
                ›
              </span>
            )}
          </button>
        </li>
      ))}
    </ul>
  );
}
