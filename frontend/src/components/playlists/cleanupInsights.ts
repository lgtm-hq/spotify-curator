import type { PlaylistScanSummary } from "../../api/client";

export type { PlaylistScanSummary };

export type CleanupIssueKind = "duplicates" | "unavailable" | "skip-heavy";

export function scanSummaryToTags(
  summary: PlaylistScanSummary | undefined,
): { kind: CleanupIssueKind; count: number }[] {
  if (!summary?.full_scan) {
    return [];
  }
  return [
    { kind: "duplicates", count: summary.duplicate_tracks },
    { kind: "unavailable", count: summary.unavailable_tracks },
  ];
}

export function hasScanData(summary: PlaylistScanSummary | undefined): boolean {
  return Boolean(summary?.full_scan);
}

export function hasCleanupIssues(summary: PlaylistScanSummary | undefined): boolean {
  return scanSummaryToTags(summary).length > 0;
}

export const cleanupTagStyles: Record<CleanupIssueKind, { label: string; className: string }> = {
  duplicates: {
    label: "Duplicates",
    className: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  },
  unavailable: {
    label: "Unavailable",
    className: "bg-red-500/15 text-red-300 border-red-500/30",
  },
  "skip-heavy": {
    label: "Skip-heavy",
    className: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  },
};

export function issueRowClass(issues: CleanupIssueKind[]): string {
  if (issues.includes("unavailable")) {
    return "border-l-2 border-l-red-500/60 bg-red-500/5";
  }
  if (issues.includes("duplicates")) {
    return "border-l-2 border-l-amber-500/60 bg-amber-500/5";
  }
  if (issues.includes("skip-heavy")) {
    return "border-l-2 border-l-violet-500/60 bg-violet-500/5";
  }
  return "";
}

export function playlistRowHighlightClass(summary: PlaylistScanSummary | undefined): string {
  if (!summary) {
    return "";
  }
  if (summary.unavailable_tracks > 0) {
    return "border-l-2 border-l-red-500/50";
  }
  if (summary.duplicate_tracks > 0) {
    return "border-l-2 border-l-amber-500/50";
  }
  return "";
}
