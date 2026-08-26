export const SPOTIFY_USAGE_INVALIDATE = "spotify-usage-invalidate";

export function notifySpotifyUsageInvalidate(): void {
  window.dispatchEvent(new Event(SPOTIFY_USAGE_INVALIDATE));
}
