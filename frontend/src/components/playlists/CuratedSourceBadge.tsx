import type { CuratedPlaylistSource } from "../../api/client";

export function CuratedSourceBadge({
  source,
  size = "sm",
}: {
  source: CuratedPlaylistSource;
  size?: "xs" | "sm";
}) {
  const sizeClass = size === "xs" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-xs";

  const toneClass =
    source.source === "discover"
      ? "border-sky-500/30 bg-sky-500/10 text-sky-200"
      : "border-violet-500/30 bg-violet-500/10 text-violet-200";

  return (
    <span
      className={`inline-flex rounded-full border font-medium uppercase tracking-wide ${sizeClass} ${toneClass}`}
    >
      {source.label}
    </span>
  );
}
