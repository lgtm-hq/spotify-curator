import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PlaylistScanSummary } from "./cleanupInsights";
import { CleanupIssueTags } from "./CleanupIssueTags";

function scanSummary(overrides: Partial<PlaylistScanSummary> = {}): PlaylistScanSummary {
  return {
    playlist_id: "playlist-1",
    playlist_name: "Road Trip",
    track_count: 12,
    tracks_scanned: 12,
    duplicate_tracks: 2,
    unavailable_tracks: 1,
    owned: true,
    full_scan: true,
    ...overrides,
  };
}

describe("CleanupIssueTags", () => {
  it("renders cleanup counts for scanned playlists", () => {
    render(<CleanupIssueTags summary={scanSummary()} skipHeavyCount={3} />);

    expect(screen.getByText("2 duplicates")).toBeInTheDocument();
    expect(screen.getByText("1 unavailable")).toBeInTheDocument();
    expect(screen.getByText("3 skip-heavy")).toBeInTheDocument();
  });

  it("renders pending or view-only status when scan data is absent", () => {
    const { rerender } = render(<CleanupIssueTags canScan />);

    expect(screen.getByText("Not scanned")).toBeInTheDocument();

    rerender(<CleanupIssueTags viewOnly />);
    expect(screen.getByText("View only")).toBeInTheDocument();
  });
});
