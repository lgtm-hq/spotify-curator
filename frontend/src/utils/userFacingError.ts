const SPOTIFY_NOISE = /spotify api error|http status:|api\.spotify\.com|code:\s*-?\d+/i;

export function userFacingError(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (error instanceof Error && error.name === "RequestCancelledError") {
    return "Cancelled.";
  }

  const raw = error instanceof Error ? error.message : typeof error === "string" ? error : fallback;
  const lower = raw.toLowerCase();

  if (lower === "cancelled" || lower === "cancelled.") {
    return "Cancelled.";
  }

  if (
    lower.includes("429") ||
    lower.includes("too many requests") ||
    lower.includes("rate limit")
  ) {
    return "Spotify is temporarily limiting requests. Check the timer above, then try again.";
  }

  if (lower.includes("403") || lower.includes("denied")) {
    return "Spotify denied access to this playlist.";
  }

  if (lower.includes("cleanup job not found") || lower.includes("job not found")) {
    return "This scan is no longer running — the server may have restarted. Run a new scan.";
  }

  if (lower.includes("discovery run not found")) {
    return "That discovery entry is no longer in history.";
  }

  if (lower.includes("404") && lower.includes("discover")) {
    return "That action is not available — restart the backend to load the latest API.";
  }

  if (lower === "not found" || lower.startsWith("request failed: 404")) {
    return "That action is not available — restart the backend to load the latest API.";
  }

  if (lower.includes("404")) {
    return "That action is not available — restart the backend to load the latest API.";
  }

  if (lower.includes("not found")) {
    return "This playlist could not be found.";
  }

  if (lower.includes("request timed out") || lower.includes("timed out")) {
    return "That took too long. Try again in a moment.";
  }

  if (
    lower.includes("not authenticated") ||
    lower.includes("spotify not connected") ||
    lower.includes("token expired") ||
    (lower.includes("401") && lower.includes("unauthorized"))
  ) {
    return "Your Spotify session expired. Reconnect Spotify to continue.";
  }

  if (SPOTIFY_NOISE.test(raw)) {
    return "Spotify couldn't complete that request right now. Try again shortly.";
  }

  if (raw.length > 140) {
    return fallback;
  }

  return raw;
}
