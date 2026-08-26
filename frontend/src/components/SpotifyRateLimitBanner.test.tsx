import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SpotifyUsageStatus } from "../api/client";
import { SpotifyRateLimitBanner } from "./SpotifyRateLimitBanner";

function usageStatus(overrides: Partial<SpotifyUsageStatus>): SpotifyUsageStatus {
  return {
    state: "ok",
    requests_in_window: 0,
    window_seconds: 30,
    estimated_limit: 100,
    usage_percent: 0,
    rate_limited_until: null,
    seconds_until_reset: null,
    last_fetched_at: null,
    ...overrides,
  };
}

describe("SpotifyRateLimitBanner", () => {
  it("renders the countdown when Spotify is rate limited", () => {
    render(
      <SpotifyRateLimitBanner usage={usageStatus({ state: "limited", seconds_until_reset: 65 })} />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Spotify rate limit active");
    expect(screen.getByText("1m 5s")).toBeInTheDocument();
  });

  it("renders nothing when usage is not limited", () => {
    const { container } = render(
      <SpotifyRateLimitBanner usage={usageStatus({ state: "warning" })} />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
