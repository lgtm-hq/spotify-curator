import { beforeEach, describe, expect, it } from "vitest";
import {
  clearAdvisorSession,
  clearJsonSession,
  loadAdvisorSession,
  loadCurateSession,
  loadJsonSession,
  saveAdvisorSession,
  saveCurateSession,
  saveJsonSession,
} from "./pageSessionStorage";

interface SavedSession {
  runId: string;
  selectedIds: string[];
}

describe("pageSessionStorage", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("saves, loads, and clears keyed JSON values", () => {
    const session: SavedSession = { runId: "run-1", selectedIds: ["a", "b"] };

    saveJsonSession("test-session", session);
    expect(loadJsonSession<SavedSession>("test-session")).toEqual(session);

    clearJsonSession("test-session");
    expect(loadJsonSession<SavedSession>("test-session")).toBeNull();
  });

  it("returns null for missing or invalid JSON", () => {
    expect(loadJsonSession<SavedSession>("missing")).toBeNull();

    sessionStorage.setItem("broken", "{not json");
    expect(loadJsonSession<SavedSession>("broken")).toBeNull();
  });

  it("uses isolated page-specific session keys", () => {
    saveAdvisorSession({ runId: "advisor" });
    saveCurateSession({ runId: "curate" });

    expect(loadAdvisorSession<{ runId: string }>()).toEqual({ runId: "advisor" });
    expect(loadCurateSession<{ runId: string }>()).toEqual({ runId: "curate" });

    clearAdvisorSession();
    expect(loadAdvisorSession<{ runId: string }>()).toBeNull();
    expect(loadCurateSession<{ runId: string }>()).toEqual({ runId: "curate" });
  });
});
