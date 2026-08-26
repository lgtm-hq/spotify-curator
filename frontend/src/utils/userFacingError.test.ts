import { describe, expect, it } from "vitest";
import { userFacingError } from "./userFacingError";

describe("userFacingError", () => {
  it.each([
    {
      error: "429 Too Many Requests",
      expected: "Spotify is temporarily limiting requests. Check the timer above, then try again.",
    },
    {
      error: "Spotify API error: code: -1",
      expected: "Spotify couldn't complete that request right now. Try again shortly.",
    },
    {
      error: "Request failed: 404",
      expected: "That action is not available — restart the backend to load the latest API.",
    },
    {
      error: "Spotify not connected",
      expected: "Your Spotify session expired. Reconnect Spotify to continue.",
    },
  ])("maps '$error' to a helpful message", ({ error, expected }) => {
    expect(userFacingError(error)).toBe(expected);
  });

  it("normalizes request cancellation errors", () => {
    const error = new Error("User aborted request");
    error.name = "RequestCancelledError";

    expect(userFacingError(error)).toBe("Cancelled.");
  });

  it("uses the fallback for long raw errors", () => {
    const fallback = "Friendly fallback.";
    const error = "x".repeat(141);

    expect(userFacingError(error, fallback)).toBe(fallback);
  });
});
