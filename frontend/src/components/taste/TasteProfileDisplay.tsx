import { useMemo, useState } from "react";
import type { TasteProfile } from "../../api/client";

function summaryInsights(summary: string): string[] {
  const trimmed = summary.trim();
  if (!trimmed) {
    return [];
  }
  const bySentence = trimmed
    .split(/(?<=[.!?])\s+/)
    .map((part) => part.trim())
    .filter((part) => part.length > 12);
  if (bySentence.length > 1) {
    return bySentence;
  }
  return trimmed
    .split(/\s*[—–;]\s+/)
    .map((part) => part.trim())
    .filter((part) => part.length > 12);
}

function confidenceLabel(confidence: string | undefined): string | null {
  if (!confidence) {
    return null;
  }
  const normalized = confidence.toLowerCase();
  if (normalized === "high") {
    return "High confidence";
  }
  if (normalized === "medium") {
    return "Medium confidence";
  }
  if (normalized === "low") {
    return "Low confidence";
  }
  return null;
}

function TasteTag({ label, variant }: { label: string; variant: "genre" | "mood" | "avoid" }) {
  const styles =
    variant === "genre"
      ? "bg-emerald-500/10 text-emerald-300"
      : variant === "mood"
        ? "bg-violet-500/10 text-violet-300"
        : "bg-rose-500/10 text-rose-300";
  return <span className={`rounded-full px-3 py-1 text-sm ${styles}`}>{label}</span>;
}

export function TasteProfileDisplay({
  profile,
  compact = false,
  className = "",
}: {
  profile: TasteProfile;
  compact?: boolean;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const insights = useMemo(() => summaryInsights(profile.summary), [profile.summary]);
  const previewCount = compact ? 2 : 3;
  const visibleInsights = expanded ? insights : insights.slice(0, previewCount);
  const hasHiddenInsights = insights.length > previewCount;
  const lanes = profile.taste_lanes ?? [];
  const hints = profile.curation_hints ?? [];
  const avoid = profile.avoid ?? [];
  const confidence = confidenceLabel(profile.confidence);
  const showCoreCurrent =
    Boolean(profile.core_taste?.trim()) || Boolean(profile.recent_shift?.trim());
  const showLanes = lanes.length > 0 && !compact;
  const showHints = hints.length > 0 && !compact;
  const showAvoid = avoid.length > 0 && !compact;
  const showAudioSummary = Boolean(profile.audio_features_summary?.trim()) && !compact;

  return (
    <div
      className={`rounded-xl border border-white/10 bg-white/[0.03] ${compact ? "p-3" : "p-4"} ${className}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        {(profile.genres.length > 0 || profile.mood_tags.length > 0) && (
          <div className="flex flex-wrap gap-2">
            {profile.genres.map((genre) => (
              <TasteTag key={`genre-${genre}`} label={genre} variant="genre" />
            ))}
            {profile.mood_tags.map((tag) => (
              <TasteTag key={`mood-${tag}`} label={tag} variant="mood" />
            ))}
          </div>
        )}
        {confidence && <span className="ml-auto text-xs text-zinc-500">{confidence}</span>}
      </div>

      {(profile.era_preference || profile.energy_range) && (
        <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs">
          {profile.era_preference && (
            <div>
              <dt className="text-zinc-500">Era</dt>
              <dd className="text-zinc-300">{profile.era_preference}</dd>
            </div>
          )}
          {profile.energy_range && (
            <div>
              <dt className="text-zinc-500">Energy</dt>
              <dd className="text-zinc-300">{profile.energy_range}</dd>
            </div>
          )}
        </dl>
      )}

      {visibleInsights.length > 0 ? (
        <ul
          className={`space-y-2 ${profile.genres.length > 0 || profile.mood_tags.length > 0 ? "mt-3" : ""}`}
        >
          {visibleInsights.map((insight) => (
            <li key={insight} className="flex gap-2 text-sm leading-relaxed text-zinc-400">
              <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-emerald-400/80" />
              <span>{insight}</span>
            </li>
          ))}
        </ul>
      ) : (
        profile.summary && (
          <p className="mt-3 text-sm leading-relaxed text-zinc-400">{profile.summary}</p>
        )
      )}

      {hasHiddenInsights && (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-2 text-xs text-emerald-400 hover:underline"
        >
          {expanded ? "Show less" : `Show ${insights.length - previewCount} more`}
        </button>
      )}

      {showCoreCurrent && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {profile.core_taste?.trim() && (
            <div className="rounded-lg border border-white/5 bg-black/20 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Core taste
              </p>
              <p className="mt-1 text-sm leading-relaxed text-zinc-300">{profile.core_taste}</p>
            </div>
          )}
          {profile.recent_shift?.trim() && (
            <div className="rounded-lg border border-white/5 bg-black/20 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Recent shift
              </p>
              <p className="mt-1 text-sm leading-relaxed text-zinc-300">{profile.recent_shift}</p>
            </div>
          )}
        </div>
      )}

      {showLanes && (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Taste lanes</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {lanes.map((lane) => (
              <div key={lane.label} className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-sm font-medium text-zinc-200">{lane.label}</p>
                {lane.description && (
                  <p className="mt-1 text-sm leading-relaxed text-zinc-400">{lane.description}</p>
                )}
                {lane.artists.length > 0 && (
                  <p className="mt-2 text-xs text-zinc-500">{lane.artists.join(" · ")}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {showHints && (
        <div className="mt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Curation hints
          </p>
          <ul className="mt-2 space-y-1.5">
            {hints.map((hint) => (
              <li key={hint} className="flex gap-2 text-sm leading-relaxed text-zinc-400">
                <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-violet-400/80" />
                <span>{hint}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {showAvoid && (
        <div className="mt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Deprioritize</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {avoid.map((item) => (
              <TasteTag key={`avoid-${item}`} label={item} variant="avoid" />
            ))}
          </div>
        </div>
      )}

      {showAudioSummary && (
        <p className="mt-4 text-xs leading-relaxed text-zinc-500">
          {profile.audio_features_summary}
        </p>
      )}
    </div>
  );
}

export function TasteProfileSkeleton({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={`space-y-3 rounded-xl border border-white/10 bg-white/[0.03] ${compact ? "p-3" : "p-4"}`}
    >
      <div className="flex flex-wrap gap-2">
        <div className="h-7 w-16 animate-pulse rounded-full bg-white/10" />
        <div className="h-7 w-20 animate-pulse rounded-full bg-white/10" />
        <div className="h-7 w-14 animate-pulse rounded-full bg-white/10" />
      </div>
      <div className="h-3 w-full animate-pulse rounded bg-white/10" />
      <div className="h-3 w-4/5 animate-pulse rounded bg-white/10" />
    </div>
  );
}
