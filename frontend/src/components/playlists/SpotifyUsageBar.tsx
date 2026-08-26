import type { SpotifyUsageStatus } from "../../api/client";

function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) {
    return "Never";
  }
  const then = new Date(iso).getTime();
  const diffSec = Math.round((Date.now() - then) / 1000);
  if (diffSec < 60) {
    return "Just now";
  }
  if (diffSec < 3600) {
    const mins = Math.round(diffSec / 60);
    return `${mins} min${mins === 1 ? "" : "s"} ago`;
  }
  if (diffSec < 86400) {
    const hours = Math.round(diffSec / 3600);
    return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  }
  return new Date(iso).toLocaleString();
}

function usageBarClass(state: SpotifyUsageStatus["state"]): string {
  if (state === "warning") {
    return "bg-amber-500";
  }
  return "bg-emerald-500";
}

function usageTextClass(state: SpotifyUsageStatus["state"]): string {
  if (state === "warning") {
    return "text-amber-300";
  }
  return "text-zinc-400";
}

/** Playlist fetch controls — rate limit countdown lives in the global banner. */
export function SpotifyUsageBar({
  usage,
  lastFetchedAt,
  onRefresh,
  refreshing,
  refreshLabel = "Refresh playlists",
}: {
  usage: SpotifyUsageStatus | null | undefined;
  lastFetchedAt?: string | null;
  onRefresh: () => void;
  refreshing?: boolean;
  refreshLabel?: string;
}) {
  const limited = usage?.state === "limited";
  const fetchedLabel = formatRelativeTime(lastFetchedAt ?? usage?.last_fetched_at);
  const percent = usage?.usage_percent ?? 0;
  const barClass = usage ? usageBarClass(usage.state) : "bg-zinc-600";

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-sm text-zinc-300">
            Last fetched: <span className="text-zinc-100">{fetchedLabel}</span>
          </p>
          {usage && !limited && (
            <p className={`text-xs ${usageTextClass(usage.state)}`}>
              API load ~{usage.usage_percent}% · {usage.requests_in_window} requests in the last{" "}
              {usage.window_seconds}s (est. limit {usage.estimated_limit})
            </p>
          )}
          {limited && (
            <p className="text-xs text-zinc-500">Refresh paused while rate limit is active</p>
          )}
        </div>
        <button
          type="button"
          disabled={refreshing || limited}
          onClick={onRefresh}
          className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-black hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {refreshing ? "Refreshing…" : refreshLabel}
        </button>
      </div>
      {usage && !limited && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
          <div
            className={`h-full transition-all duration-500 ${barClass}`}
            style={{ width: `${Math.max(percent, 4)}%` }}
          />
        </div>
      )}
    </div>
  );
}
