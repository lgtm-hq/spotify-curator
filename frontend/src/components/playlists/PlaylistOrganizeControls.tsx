import { useEffect, useId, useRef, useState } from "react";
import {
  defaultPlaylistSortKey,
  PlaylistSortKey,
  playlistSortOptions,
  savePlaylistSortKey,
} from "./playlistSort";

function sortLabel(sortKey: PlaylistSortKey): string {
  return (
    playlistSortOptions.find((option) => option.value === sortKey)?.label ?? "Spotify library order"
  );
}

function applySort(sortKey: PlaylistSortKey, onSortChange: (sortKey: PlaylistSortKey) => void) {
  savePlaylistSortKey(sortKey);
  onSortChange(sortKey);
}

export function PlaylistOrganizeControls({
  sortKey,
  onSortChange,
}: {
  sortKey: PlaylistSortKey;
  onSortChange: (sortKey: PlaylistSortKey) => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const isDefaultSort = sortKey === defaultPlaylistSortKey;

  useEffect(() => {
    if (!open) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const handleOptionSelect = (optionValue: PlaylistSortKey) => {
    if (optionValue === sortKey) {
      applySort(defaultPlaylistSortKey, onSortChange);
    } else {
      applySort(optionValue, onSortChange);
    }
    setOpen(false);
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((current) => !current)}
        className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-zinc-300 transition hover:bg-white/5"
      >
        <span className="text-zinc-500">Sort</span>
        <span className={isDefaultSort ? "text-zinc-400" : "text-zinc-200"}>
          {sortLabel(sortKey)}
        </span>
        <span aria-hidden className="text-[10px] text-zinc-500">
          {open ? "▴" : "▾"}
        </span>
      </button>

      {open && (
        <div
          id={menuId}
          role="listbox"
          aria-label="Sort playlists"
          className="absolute right-0 z-20 mt-2 min-w-[15rem] overflow-hidden rounded-lg border border-white/10 bg-zinc-950 py-1 shadow-xl"
        >
          {playlistSortOptions.map((option) => {
            const selected = option.value === sortKey;
            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={selected}
                title={selected ? "Click again to reset to default sort" : undefined}
                onClick={() => handleOptionSelect(option.value)}
                className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition ${
                  selected ? "bg-emerald-500/10 text-emerald-200" : "text-zinc-300 hover:bg-white/5"
                }`}
              >
                <span className="w-4 shrink-0 text-xs">{selected ? "✓" : ""}</span>
                <span>{option.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
