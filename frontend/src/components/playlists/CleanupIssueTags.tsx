import {
  cleanupTagStyles,
  hasScanData,
  type CleanupIssueKind,
  type PlaylistScanSummary,
  scanSummaryToTags,
} from "./cleanupInsights";

function zeroTagClassName(kind: CleanupIssueKind, size: "sm" | "xs"): string {
  const textSize = size === "xs" ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-0.5";
  const styles: Record<CleanupIssueKind, string> = {
    duplicates: "border-amber-500/25 bg-amber-500/10 text-amber-200/90",
    unavailable: "border-red-500/25 bg-red-500/10 text-red-200/90",
    "skip-heavy": "border-violet-500/25 bg-violet-500/10 text-violet-200/90",
  };
  return `${textSize} border font-medium ${styles[kind]}`;
}

function tagClassName(kind: CleanupIssueKind, count: number, size: "sm" | "xs"): string {
  const textSize = size === "xs" ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-0.5";
  if (count === 0) {
    return zeroTagClassName(kind, size);
  }
  return `${textSize} border font-medium ${cleanupTagStyles[kind].className}`;
}

function statusPillClass(size: "sm" | "xs", variant: "pending" | "view-only"): string {
  const textSize = size === "xs" ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-0.5";
  if (variant === "view-only") {
    return `${textSize} rounded-full border border-sky-500/25 bg-sky-500/10 font-medium text-sky-200/90`;
  }
  return `${textSize} rounded-full border border-white/15 bg-white/[0.06] font-medium text-zinc-300`;
}

export function CleanupIssueTags({
  summary,
  canScan = false,
  viewOnly = false,
  skipHeavyCount = 0,
  size = "sm",
}: {
  summary?: PlaylistScanSummary;
  canScan?: boolean;
  viewOnly?: boolean;
  skipHeavyCount?: number;
  size?: "sm" | "xs";
}) {
  if (!hasScanData(summary)) {
    if (canScan) {
      return <span className={statusPillClass(size, "pending")}>Not scanned</span>;
    }
    if (viewOnly) {
      return <span className={statusPillClass(size, "view-only")}>View only</span>;
    }
    return null;
  }

  const tags = scanSummaryToTags(summary);
  if (skipHeavyCount > 0) {
    tags.push({ kind: "skip-heavy", count: skipHeavyCount });
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((tag) => (
        <span key={tag.kind} className={`rounded-full ${tagClassName(tag.kind, tag.count, size)}`}>
          {tag.count} {cleanupTagStyles[tag.kind].label.toLowerCase()}
        </span>
      ))}
    </div>
  );
}

export function CleanupSummaryBanner({
  summary,
  skipHeavyCount,
  onRemoveDuplicates,
  onRemoveUnavailable,
  onRemoveSkipHeavy,
  busy,
}: {
  summary?: PlaylistScanSummary;
  skipHeavyCount?: number;
  onRemoveDuplicates?: () => void;
  onRemoveUnavailable?: () => void;
  onRemoveSkipHeavy?: () => void;
  busy?: boolean;
}) {
  const dupes = summary?.duplicate_tracks ?? 0;
  const unavail = summary?.unavailable_tracks ?? 0;
  const skip = skipHeavyCount ?? 0;

  if (!hasScanData(summary) && skip === 0) {
    return null;
  }

  return (
    <div className="border-b border-white/10 bg-white/5 px-4 py-3">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
        Cleanup insights
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <CleanupIssueTags summary={summary} canScan skipHeavyCount={skipHeavyCount} />
        {dupes > 0 && onRemoveDuplicates && (
          <ActionChip
            kind="duplicates"
            count={dupes}
            disabled={busy}
            onClick={onRemoveDuplicates}
          />
        )}
        {unavail > 0 && onRemoveUnavailable && (
          <ActionChip
            kind="unavailable"
            count={unavail}
            disabled={busy}
            onClick={onRemoveUnavailable}
          />
        )}
        {skip > 0 && onRemoveSkipHeavy && (
          <ActionChip kind="skip-heavy" count={skip} disabled={busy} onClick={onRemoveSkipHeavy} />
        )}
      </div>
    </div>
  );
}

function ActionChip({
  kind,
  count,
  disabled,
  onClick,
}: {
  kind: CleanupIssueKind;
  count: number;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded-md border px-2 py-1 text-xs disabled:opacity-40 ${cleanupTagStyles[kind].className}`}
    >
      Remove {count}
    </button>
  );
}
