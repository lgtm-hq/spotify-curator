import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect } from "react";
import { api, type SpotifyUsageStatus } from "../api/client";
import { SPOTIFY_USAGE_INVALIDATE } from "../utils/spotifyUsageEvents";

function usagePollInterval(state: SpotifyUsageStatus["state"] | undefined): number | false {
  if (state === "limited") {
    return 1000;
  }
  if (state === "warning") {
    return 10_000;
  }
  return 30_000;
}

export function useSpotifyUsage(options?: { enabled?: boolean }) {
  const queryClient = useQueryClient();
  const enabled = options?.enabled ?? true;

  const query = useQuery({
    queryKey: ["spotify-usage"],
    queryFn: api.spotifyUsage,
    enabled,
    retry: false,
    refetchInterval: (q) => usagePollInterval(q.state.data?.state),
  });

  useEffect(() => {
    const handler = () => {
      void queryClient.invalidateQueries({ queryKey: ["spotify-usage"] });
    };
    window.addEventListener(SPOTIFY_USAGE_INVALIDATE, handler);
    return () => window.removeEventListener(SPOTIFY_USAGE_INVALIDATE, handler);
  }, [queryClient]);

  const onLimitExpired = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["spotify-usage"] });
    void queryClient.invalidateQueries({ queryKey: ["playlists"] });
  }, [queryClient]);

  const usage = query.data;
  const rateLimited = usage?.state === "limited";

  return {
    usage,
    rateLimited,
    onLimitExpired,
    isLoading: query.isLoading,
  };
}

export type { SpotifyUsageStatus };
