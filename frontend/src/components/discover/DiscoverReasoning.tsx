import type { ReactNode } from "react";
import type { DiscoverRationale } from "../../api/client";

function ChipList({
  items,
  tone = "sky",
}: {
  items: string[];
  tone?: "sky" | "emerald" | "zinc" | "red";
}) {
  if (items.length === 0) {
    return null;
  }

  const toneClass =
    tone === "emerald"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
      : tone === "red"
        ? "border-red-500/20 bg-red-500/5 text-red-300/90"
        : tone === "zinc"
          ? "border-white/10 bg-white/5 text-zinc-400"
          : "border-sky-500/30 bg-sky-500/10 text-sky-200";

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span key={item} className={`rounded-full border px-3 py-1 text-xs ${toneClass}`}>
          {item}
        </span>
      ))}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{title}</h4>
      {children}
    </section>
  );
}

function hasStructuredRationale(rationale: DiscoverRationale): boolean {
  return Boolean(
    rationale.summary ||
    rationale.core_genres.length ||
    rationale.spotlight_artists.length ||
    rationale.discovery_picks.length ||
    rationale.energy_notes ||
    rationale.flow_strategy ||
    rationale.excluded.length,
  );
}

export function DiscoverReasoning({
  reasoning,
  rationale,
}: {
  reasoning: string;
  rationale: DiscoverRationale;
}) {
  if (!hasStructuredRationale(rationale)) {
    return (
      <details className="rounded-lg border border-white/10 bg-black/20 px-4 py-3">
        <summary className="cursor-pointer text-sm text-zinc-400">Why these picks?</summary>
        <p className="mt-3 text-sm leading-relaxed text-zinc-300">
          {reasoning || "No curation notes available."}
        </p>
      </details>
    );
  }

  return (
    <div className="space-y-5 rounded-lg border border-white/10 bg-black/20 p-4">
      <div>
        <h4 className="text-sm font-medium text-zinc-200">Why these picks?</h4>
        {rationale.summary && (
          <p className="mt-2 text-sm leading-relaxed text-zinc-300">{rationale.summary}</p>
        )}
      </div>

      {rationale.core_genres.length > 0 && (
        <Section title="Core genres">
          <ChipList items={rationale.core_genres} tone="sky" />
        </Section>
      )}

      {rationale.spotlight_artists.length > 0 && (
        <Section title="Spotlight artists">
          <ChipList items={rationale.spotlight_artists} tone="emerald" />
        </Section>
      )}

      {rationale.discovery_picks.length > 0 && (
        <Section title="Discovery picks">
          <ChipList items={rationale.discovery_picks} tone="emerald" />
        </Section>
      )}

      {rationale.energy_notes && (
        <Section title="Energy & texture">
          <p className="text-sm leading-relaxed text-zinc-300">{rationale.energy_notes}</p>
        </Section>
      )}

      {rationale.flow_strategy && (
        <Section title="Flow strategy">
          <p className="text-sm leading-relaxed text-zinc-300">{rationale.flow_strategy}</p>
        </Section>
      )}

      {rationale.excluded.length > 0 && (
        <Section title="Left out">
          <ChipList items={rationale.excluded} tone="red" />
        </Section>
      )}

      {reasoning && rationale.summary && reasoning !== rationale.summary && (
        <details className="rounded-lg border border-white/5 bg-white/5 px-3 py-2">
          <summary className="cursor-pointer text-xs text-zinc-500">Full AI notes</summary>
          <p className="mt-2 text-sm leading-relaxed text-zinc-400">{reasoning}</p>
        </details>
      )}
    </div>
  );
}
