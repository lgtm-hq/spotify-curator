export const PlaylistViewMode = {
  Tile: "tile",
  List: "list",
  Column: "column",
} as const;

export type PlaylistViewMode = (typeof PlaylistViewMode)[keyof typeof PlaylistViewMode];

const STORAGE_KEY = "spotify-curator-playlist-view";

export function loadPlaylistViewMode(): PlaylistViewMode {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (
    stored === PlaylistViewMode.Tile ||
    stored === PlaylistViewMode.List ||
    stored === PlaylistViewMode.Column
  ) {
    return stored;
  }
  return PlaylistViewMode.Tile;
}

export function savePlaylistViewMode(mode: PlaylistViewMode): void {
  localStorage.setItem(STORAGE_KEY, mode);
}

export function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function reorderPayload(fromIndex: number, toIndex: number) {
  if (fromIndex === toIndex) {
    return null;
  }
  if (fromIndex < toIndex) {
    return { range_start: fromIndex, insert_before: toIndex + 1, range_length: 1 };
  }
  return { range_start: fromIndex, insert_before: toIndex, range_length: 1 };
}
