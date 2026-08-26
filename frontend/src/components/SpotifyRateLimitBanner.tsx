import { useEffect, useState } from "react";
import type { SpotifyUsageStatus } from "../api/client";

function formatCountdown(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) {
    return "now";
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hours > 0) {
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
  if (minutes > 0) {
    return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`;
  }
  return `${secs}s`;
}

function useSpotifyRateLimitCountdown(
  usage: SpotifyUsageStatus | null | undefined,
  onExpired?: () => void,
): { countdown: number | null; limited: boolean } {
  const [countdown, setCountdown] = useState<number | null>(usage?.seconds_until_reset ?? null);
  const limited = usage?.state === "limited";

  useEffect(() => {
    setCountdown(usage?.seconds_until_reset ?? null);
  }, [usage?.seconds_until_reset]);

  useEffect(() => {
    if (!limited || usage?.seconds_until_reset == null) {
      return;
    }
    setCountdown(usage.seconds_until_reset);
    const timer = window.setInterval(() => {
      setCountdown((value) => {
        if (value == null || value <= 1) {
          return 0;
        }
        return value - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [limited, usage?.seconds_until_reset]);

  useEffect(() => {
    if (countdown === 0 && limited) {
      onExpired?.();
    }
  }, [countdown, limited, onExpired]);

  return { countdown, limited };
}

/** Live countdown banner when Spotify rate limit is active. */
export function SpotifyRateLimitBanner({
  usage,
  onLimitExpired,
  className = "",
}: {
  usage: SpotifyUsageStatus;
  onLimitExpired?: () => void;
  className?: string;
}) {
  const { countdown, limited } = useSpotifyRateLimitCountdown(usage, onLimitExpired);

  if (!limited) {
    return null;
  }

  return (
    <div
      className={`rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-red-200">Spotify rate limit active</p>
          <p className="mt-0.5 text-sm text-red-300/90">
            Spotify API calls are paused. Available again in{" "}
            <span className="font-medium text-red-200">{formatCountdown(countdown)}</span>.
          </p>
        </div>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-red-950/50">
        <div className="h-full w-full animate-pulse rounded-full bg-red-500/70" />
      </div>
    </div>
  );
}
