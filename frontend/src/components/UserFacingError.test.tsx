import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UserFacingError } from "./UserFacingError";

describe("UserFacingError", () => {
  it("renders a normalized error message with an optional title", () => {
    render(<UserFacingError error="token expired" title="Could not load playlists" />);

    expect(screen.getByText("Could not load playlists")).toBeInTheDocument();
    expect(
      screen.getByText("Your Spotify session expired. Reconnect Spotify to continue."),
    ).toBeInTheDocument();
  });

  it("calls onRetry from the retry button", () => {
    const onRetry = vi.fn();

    render(<UserFacingError error="Request failed" onRetry={onRetry} retryLabel="Reload" />);
    fireEvent.click(screen.getByRole("button", { name: "Reload" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
