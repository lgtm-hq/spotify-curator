import { PlaylistViewMode, type PlaylistViewMode as ViewMode } from "./viewMode";

const modes: { id: ViewMode; label: string; icon: string }[] = [
  { id: PlaylistViewMode.Tile, label: "Tiles", icon: "▦" },
  { id: PlaylistViewMode.List, label: "List", icon: "☰" },
  { id: PlaylistViewMode.Column, label: "Columns", icon: "▥" },
];

export function ViewSwitcher({
  value,
  onChange,
}: {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
}) {
  return (
    <div
      className="inline-flex rounded-lg border border-white/10 bg-black/40 p-1"
      role="group"
      aria-label="Playlist view"
    >
      {modes.map((mode) => (
        <button
          key={mode.id}
          type="button"
          title={mode.label}
          aria-label={mode.label}
          aria-pressed={value === mode.id}
          onClick={() => onChange(mode.id)}
          className={`rounded-md px-3 py-1.5 text-sm transition ${
            value === mode.id
              ? "bg-emerald-500/20 text-emerald-300"
              : "text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
          }`}
        >
          <span className="mr-1.5">{mode.icon}</span>
          {mode.label}
        </button>
      ))}
    </div>
  );
}
