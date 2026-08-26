import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  api,
  type AdvisorPreset,
  type AdvisorScanEstimate,
  type CleanupSuggestOptions,
  type PlaylistSummary,
  type TasteProfile,
} from "../../api/client";
import { ToggleSwitch } from "./ToggleSwitch";
import { SelectionCard } from "./SelectionCard";
import { TasteProfileDisplay } from "../taste/TasteProfileDisplay";
import { DEFAULT_ADVISOR_OPTIONS } from "./advisorOptions";

const CRON_PRESETS: { label: string; value: string }[] = [
  { label: "Sunday mornings (9:00)", value: "0 9 * * 0" },
  { label: "Monday mornings (9:00)", value: "0 9 * * 1" },
  { label: "Every day (9:00)", value: "0 9 * * *" },
];

const FOCUS_OPTIONS: {
  value: "duplicates" | "unavailable" | "bloated";
  label: string;
  hint: string;
}[] = [
  { value: "duplicates", label: "Duplicates", hint: "Same song twice" },
  { value: "unavailable", label: "Dead tracks", hint: "Won't play" },
  { value: "bloated", label: "Oversized", hint: "Needs a trim" },
];

const ALL_FOCUS_VALUES = FOCUS_OPTIONS.map((item) => item.value);

function toggleFocusArea(
  options: CleanupSuggestOptions,
  area: (typeof FOCUS_OPTIONS)[number]["value"],
): CleanupSuggestOptions {
  const selected = new Set(options.focus_areas);
  if (selected.has(area)) {
    if (selected.size <= 1) {
      return options;
    }
    selected.delete(area);
  } else {
    selected.add(area);
  }
  return {
    ...options,
    focus_areas: ALL_FOCUS_VALUES.filter((value) => selected.has(value)),
  };
}

function isFocusAreaSelected(
  options: CleanupSuggestOptions,
  area: (typeof FOCUS_OPTIONS)[number]["value"],
): boolean {
  return options.focus_areas.includes(area);
}

type ScopeMode = "all" | "pick";

function scopeFromOptions(options: CleanupSuggestOptions): {
  mode: ScopeMode;
  includeFollowed: boolean;
} {
  if (options.scope === "selected") {
    return { mode: "pick", includeFollowed: false };
  }
  return {
    mode: "all",
    includeFollowed: options.scope === "all_in_library",
  };
}

function applyScopeMode(
  options: CleanupSuggestOptions,
  mode: ScopeMode,
  includeFollowed: boolean,
): CleanupSuggestOptions {
  if (mode === "pick") {
    return { ...options, scope: "selected" };
  }
  return {
    ...options,
    scope: includeFollowed ? "all_in_library" : "all_owned",
  };
}

function countForScope(playlists: PlaylistSummary[], options: CleanupSuggestOptions): number {
  const excluded = new Set(options.exclude_playlist_ids);
  const eligible = playlists.filter(
    (p) => p.track_count >= options.min_track_count && !excluded.has(p.id),
  );
  if (options.scope === "all_owned") {
    return eligible.filter((p) => p.can_edit).length;
  }
  if (options.scope === "selected") {
    const selected = new Set(options.playlist_ids);
    return eligible.filter((p) => selected.has(p.id)).length;
  }
  return eligible.length;
}

function followedCount(playlists: PlaylistSummary[]): number {
  return playlists.filter((p) => !p.can_edit).length;
}

function effectiveConfigurationOptions(preset: AdvisorPreset): CleanupSuggestOptions {
  const partial = (preset.options ?? {}) as Partial<CleanupSuggestOptions> & {
    focus?: string;
  };
  const merged = { ...DEFAULT_ADVISOR_OPTIONS, ...partial };
  if (!partial.focus_areas && partial.focus) {
    merged.focus_areas =
      partial.focus === "all"
        ? [...ALL_FOCUS_VALUES]
        : [partial.focus as (typeof ALL_FOCUS_VALUES)[number]];
  }
  return merged;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds} sec`;
  }
  const minutes = Math.round(seconds / 60);
  return minutes === 1 ? "1 min" : `${minutes} min`;
}

function friendlyEstimate(estimate: AdvisorScanEstimate | undefined): string | null {
  if (!estimate) {
    return null;
  }
  if (estimate.playlist_count === 0) {
    return "No playlists match — try changing what to scan.";
  }
  const time = `${formatDuration(estimate.estimated_seconds_min)}–${formatDuration(estimate.estimated_seconds_max)}`;
  const playlists = `${estimate.playlist_count} playlist${estimate.playlist_count === 1 ? "" : "s"}`;
  if (estimate.fresh_scan_count === 0) {
    return `About ${time} · ${playlists} · using saved scan data`;
  }
  if (estimate.cached_count === 0) {
    return `About ${time} · ${playlists} · full scan`;
  }
  return `About ${time} · ${playlists} · ${estimate.cached_count} already scanned, ${estimate.fresh_scan_count} to refresh`;
}

export function AiAdvisorConfig({
  options,
  onChange,
  playlists,
  tasteProfile,
  disabled,
}: {
  options: CleanupSuggestOptions;
  onChange: (next: CleanupSuggestOptions) => void;
  playlists: PlaylistSummary[];
  tasteProfile?: TasteProfile | null;
  disabled?: boolean;
}) {
  const queryClient = useQueryClient();
  const [playlistFilter, setPlaylistFilter] = useState("");
  const [excludeFilter, setExcludeFilter] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showSavePreset, setShowSavePreset] = useState(false);
  const [presetName, setPresetName] = useState("");
  const [debouncedOptions, setDebouncedOptions] = useState(options);
  const [scheduleCron, setScheduleCron] = useState("0 9 * * 0");
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [scheduleNotify, setScheduleNotify] = useState(true);

  const { mode: scopeMode, includeFollowed } = scopeFromOptions(options);
  const followedPlaylistCount = useMemo(() => followedCount(playlists), [playlists]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedOptions(options), 400);
    return () => window.clearTimeout(timer);
  }, [options]);

  const presets = useQuery({
    queryKey: ["advisor-presets"],
    queryFn: async () => (await api.cleanupAiPresets()).presets,
    staleTime: 60_000,
  });

  const schedule = useQuery({
    queryKey: ["advisor-schedule"],
    queryFn: api.cleanupAiSchedule,
    staleTime: 30_000,
  });

  const scheduleRuns = useQuery({
    queryKey: ["advisor-schedule-runs"],
    queryFn: async () => (await api.cleanupAiScheduleRuns()).runs,
    enabled: showAdvanced,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (schedule.data) {
      setScheduleEnabled(schedule.data.enabled);
      setScheduleCron(schedule.data.cron);
      setScheduleNotify(schedule.data.notify_email);
    }
  }, [schedule.data]);

  const estimate = useQuery({
    queryKey: ["advisor-estimate", debouncedOptions],
    queryFn: () => api.cleanupAiEstimate(debouncedOptions),
    enabled: playlists.length > 0,
    staleTime: 10_000,
    retry: false,
  });

  const savePreset = useMutation({
    mutationFn: () =>
      api.cleanupAiPresetSave({
        name: presetName.trim(),
        options,
      }),
    onSuccess: async () => {
      setPresetName("");
      setShowSavePreset(false);
      await queryClient.invalidateQueries({ queryKey: ["advisor-presets"] });
    },
  });

  const deletePreset = useMutation({
    mutationFn: (presetId: string) => api.cleanupAiPresetDelete(presetId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["advisor-presets"] });
    },
  });

  const saveSchedule = useMutation({
    mutationFn: () =>
      api.cleanupAiScheduleUpdate({
        enabled: scheduleEnabled,
        cron: scheduleCron,
        options,
        notify_email: scheduleNotify,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["advisor-schedule"] });
      await queryClient.invalidateQueries({ queryKey: ["advisor-schedule-runs"] });
    },
  });

  const scanCount = useMemo(() => countForScope(playlists, options), [playlists, options]);

  const filteredPlaylists = useMemo(() => {
    const query = playlistFilter.trim().toLowerCase();
    const sorted = [...playlists].sort((a, b) => a.name.localeCompare(b.name));
    if (!query) {
      return sorted;
    }
    return sorted.filter((p) => p.name.toLowerCase().includes(query));
  }, [playlists, playlistFilter]);

  const filteredExcludes = useMemo(() => {
    const query = excludeFilter.trim().toLowerCase();
    const sorted = [...playlists].sort((a, b) => a.name.localeCompare(b.name));
    if (!query) {
      return sorted;
    }
    return sorted.filter((p) => p.name.toLowerCase().includes(query));
  }, [playlists, excludeFilter]);

  const togglePlaylist = (playlistId: string) => {
    const selected = new Set(options.playlist_ids);
    if (selected.has(playlistId)) {
      selected.delete(playlistId);
    } else {
      selected.add(playlistId);
    }
    onChange({ ...options, playlist_ids: [...selected] });
  };

  const toggleExclude = (playlistId: string) => {
    const excluded = new Set(options.exclude_playlist_ids);
    if (excluded.has(playlistId)) {
      excluded.delete(playlistId);
    } else {
      excluded.add(playlistId);
    }
    onChange({ ...options, exclude_playlist_ids: [...excluded] });
  };

  const selectQuickStart = (presetId: string) => {
    onChange({ ...options, quick_start_id: presetId });
  };

  const applySavedConfiguration = (preset: AdvisorPreset) => {
    if (!preset.options) {
      return;
    }
    const quickStartId = options.quick_start_id;
    onChange({
      ...effectiveConfigurationOptions(preset),
      quick_start_id: quickStartId,
    });
  };

  const estimateLine = friendlyEstimate(estimate.data);
  const allPresets = presets.data ?? [];
  const quickStartPresets = allPresets.filter(
    (p) => p.kind === "intent" || (p.builtin && !p.options),
  );
  const savedConfigurations = allPresets.filter((p) => p.kind === "configuration");
  const activeQuickStartId = options.quick_start_id;

  return (
    <div className="space-y-6">
      {/* Quick start */}
      <section className="rounded-xl border border-white/10 bg-black/25 p-4">
        <h4 className="text-sm font-medium text-zinc-100">Quick start</h4>
        <p className="mt-1 text-xs text-zinc-500">
          Sets how the AI prioritizes suggestions. Scan settings below stay independent.
        </p>
        <div
          className="mt-4 grid gap-2 sm:grid-cols-2"
          role="radiogroup"
          aria-label="Quick start approaches"
        >
          {quickStartPresets.map((preset) => {
            const isActive = activeQuickStartId === preset.id;
            return (
              <SelectionCard
                key={preset.id}
                role="radio"
                selected={isActive}
                ariaChecked={isActive}
                disabled={disabled}
                onClick={() => selectQuickStart(preset.id)}
                title={preset.name}
                description={preset.description}
              />
            );
          })}
        </div>
        {(savedConfigurations.length > 0 || showSavePreset) && (
          <div className="mt-4 border-t border-white/5 pt-4">
            <p className="mb-2 text-xs text-zinc-500">
              Saved scan configurations — loads scope & filters, not the AI approach above.
            </p>
            {savedConfigurations.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-2">
                {savedConfigurations.map((preset) => (
                  <div key={preset.id} className="flex items-center">
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => applySavedConfiguration(preset)}
                      className="rounded-full border border-white/10 px-3 py-1 text-xs text-zinc-300 transition hover:border-violet-400/40"
                    >
                      {preset.name}
                    </button>
                    <button
                      type="button"
                      disabled={disabled || deletePreset.isPending}
                      onClick={() => deletePreset.mutate(preset.id)}
                      className="ml-1 px-1 text-xs text-zinc-600 hover:text-red-300"
                      aria-label={`Delete ${preset.name}`}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
            {showSavePreset ? (
              <div className="flex flex-wrap gap-2">
                <input
                  type="text"
                  value={presetName}
                  onChange={(e) => setPresetName(e.target.value)}
                  placeholder="Preset name…"
                  disabled={disabled}
                  className="min-w-[10rem] flex-1 rounded-lg border border-white/10 bg-black px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  disabled={disabled || !presetName.trim() || savePreset.isPending}
                  onClick={() => savePreset.mutate()}
                  className="rounded-lg bg-violet-500/20 px-3 py-2 text-sm text-violet-200"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => setShowSavePreset(false)}
                  className="px-2 text-sm text-zinc-500"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                disabled={disabled}
                onClick={() => setShowSavePreset(true)}
                className="text-xs text-violet-300 hover:underline"
              >
                Save current scan settings
              </button>
            )}
          </div>
        )}
        {!showSavePreset && savedConfigurations.length === 0 && (
          <button
            type="button"
            disabled={disabled}
            onClick={() => setShowSavePreset(true)}
            className="mt-3 text-xs text-zinc-500 hover:text-violet-300"
          >
            Save current scan settings
          </button>
        )}
      </section>

      {estimateLine && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-100">
          <span className="text-emerald-400">⏱</span>
          {estimate.isFetching ? "Calculating…" : estimateLine}
        </div>
      )}

      {/* What to scan */}
      <ConfigSection title="What to scan" description="Which playlists should the advisor look at?">
        <SegmentedControl
          disabled={disabled}
          value={scopeMode}
          onChange={(mode) => onChange(applyScopeMode(options, mode, includeFollowed))}
          options={[
            { value: "all", label: "All my playlists" },
            { value: "pick", label: "Choose playlists" },
          ]}
        />

        {scopeMode === "all" && (
          <div className="mt-4 rounded-lg bg-white/[0.03] px-3 py-3">
            <ToggleSwitch
              id="include-followed"
              checked={includeFollowed}
              disabled={disabled || followedPlaylistCount === 0}
              onChange={(checked) => onChange(applyScopeMode(options, "all", checked))}
              label="Include playlists I follow"
              description={
                followedPlaylistCount > 0
                  ? `Adds ${followedPlaylistCount} playlist${followedPlaylistCount === 1 ? "" : "s"} made by others — view-only suggestions, since you can't edit them here.`
                  : "You don't follow any playlists outside your own."
              }
            />
          </div>
        )}

        <p className="mt-3 text-xs text-zinc-500">
          Ready to scan <span className="font-medium text-zinc-300">{scanCount}</span> playlist
          {scanCount === 1 ? "" : "s"}
          {scopeMode === "all" && !includeFollowed && " you own"}
          {playlists.length === 0 && (
            <>
              {" "}
              —{" "}
              <Link to="/" className="text-emerald-400 hover:underline">
                refresh on Dashboard
              </Link>{" "}
              first
            </>
          )}
        </p>

        {scopeMode === "pick" && (
          <div className="mt-4">
            <PlaylistPicker
              filter={playlistFilter}
              onFilterChange={setPlaylistFilter}
              playlists={filteredPlaylists}
              selectedIds={options.playlist_ids}
              minTrackCount={options.min_track_count}
              disabled={disabled}
              onToggle={togglePlaylist}
              onSelectVisible={() => {
                const ids = new Set(options.playlist_ids);
                for (const playlist of filteredPlaylists) {
                  if (playlist.track_count >= options.min_track_count) {
                    ids.add(playlist.id);
                  }
                }
                onChange({ ...options, playlist_ids: [...ids] });
              }}
              onClear={() => onChange({ ...options, playlist_ids: [] })}
            />
          </div>
        )}
      </ConfigSection>

      {/* What to look for */}
      <ConfigSection
        title="What to look for"
        description="Pick one or more — mix and match what matters to you."
      >
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {FOCUS_OPTIONS.map((item) => {
            const selected = isFocusAreaSelected(options, item.value);
            return (
              <SelectionCard
                key={item.value}
                selected={selected}
                ariaPressed={selected}
                disabled={disabled}
                onClick={() => onChange(toggleFocusArea(options, item.value))}
                title={item.label}
                description={item.hint}
              />
            );
          })}
        </div>
        <p className="mt-2 text-xs text-zinc-600">
          {options.focus_areas.length === 3
            ? "All issue types selected"
            : `${options.focus_areas.length} of 3 selected`}
        </p>

        <div className="mt-4">
          <label className="text-sm text-zinc-300" htmlFor="advisor-prompt">
            Anything else the AI should know?
          </label>
          <textarea
            id="advisor-prompt"
            rows={2}
            disabled={disabled}
            value={options.user_prompt ?? ""}
            onChange={(e) =>
              onChange({
                ...options,
                user_prompt: e.target.value.trim() ? e.target.value : null,
              })
            }
            placeholder='Optional — e.g. "Focus on my Afrikaans playlists first"'
            className="mt-2 w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2.5 text-sm text-zinc-200 placeholder:text-zinc-600"
          />
        </div>
      </ConfigSection>

      {/* Personalization */}
      <ConfigSection
        title="Personalization"
        description="Use your listening taste to rank what to fix first."
      >
        <ToggleSwitch
          id="include-taste"
          checked={options.include_taste_profile}
          disabled={disabled}
          onChange={(checked) => onChange({ ...options, include_taste_profile: checked })}
          label="Use my taste profile"
          description="Helps the AI prioritize playlists that match how you actually listen."
        />
        {tasteProfile && options.include_taste_profile && (
          <TasteProfileDisplay profile={tasteProfile} compact className="mt-3" />
        )}
        {options.include_taste_profile && (
          <div className="mt-3">
            <label className="text-xs text-zinc-500" htmlFor="custom-taste">
              Override for this run (optional)
            </label>
            <textarea
              id="custom-taste"
              rows={2}
              disabled={disabled}
              value={options.custom_taste_summary ?? ""}
              onChange={(e) =>
                onChange({
                  ...options,
                  custom_taste_summary: e.target.value.trim() ? e.target.value : null,
                })
              }
              placeholder='e.g. "Ignore workout playlists — focus on chill and acoustic"'
              className="mt-1 w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm placeholder:text-zinc-600"
            />
          </div>
        )}
      </ConfigSection>

      {/* Advanced */}
      <section className="rounded-xl border border-white/10 bg-black/20">
        <button
          type="button"
          onClick={() => setShowAdvanced((value) => !value)}
          className="flex w-full items-center justify-between px-4 py-3.5 text-left"
        >
          <div>
            <span className="text-sm font-medium text-zinc-200">Fine-tune scan</span>
            <p className="mt-0.5 text-xs text-zinc-500">
              Exclusions, thresholds, performance & scheduling
            </p>
          </div>
          <span className="text-zinc-500">{showAdvanced ? "−" : "+"}</span>
        </button>

        {showAdvanced && (
          <div className="space-y-5 border-t border-white/5 px-4 pb-4 pt-4">
            <SubBlock title="Skip these playlists">
              <PlaylistPicker
                filter={excludeFilter}
                onFilterChange={setExcludeFilter}
                playlists={filteredExcludes}
                selectedIds={options.exclude_playlist_ids}
                minTrackCount={0}
                disabled={disabled}
                onToggle={toggleExclude}
                onSelectVisible={() => {
                  const ids = new Set(options.exclude_playlist_ids);
                  for (const playlist of filteredExcludes) {
                    ids.add(playlist.id);
                  }
                  onChange({ ...options, exclude_playlist_ids: [...ids] });
                }}
                onClear={() => onChange({ ...options, exclude_playlist_ids: [] })}
              />
            </SubBlock>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Scan order">
                <select
                  disabled={disabled}
                  value={options.sort_by}
                  onChange={(e) =>
                    onChange({
                      ...options,
                      sort_by: e.target.value as CleanupSuggestOptions["sort_by"],
                    })
                  }
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-zinc-200"
                >
                  <option value="track_count_desc">Largest first</option>
                  <option value="track_count_asc">Smallest first</option>
                  <option value="name_asc">Name A–Z</option>
                  <option value="name_desc">Name Z–A</option>
                  <option value="stale_first">Needs rescan first</option>
                  <option value="recently_scanned">Recently scanned first</option>
                </select>
              </Field>
              <Field label="Only rescan if older than">
                <select
                  disabled={disabled}
                  value={options.stale_after_days ?? ""}
                  onChange={(e) =>
                    onChange({
                      ...options,
                      stale_after_days: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-zinc-200"
                >
                  <option value="">No limit</option>
                  <option value="7">7 days</option>
                  <option value="14">14 days</option>
                  <option value="30">30 days</option>
                  <option value="90">90 days</option>
                </select>
              </Field>
            </div>

            <SubBlock title="Only show playlists with at least…">
              <div className="grid gap-4 sm:grid-cols-3">
                <ThresholdField
                  label="Duplicates"
                  value={options.min_duplicates}
                  max={20}
                  disabled={disabled}
                  onChange={(value) => onChange({ ...options, min_duplicates: value })}
                />
                <ThresholdField
                  label="Dead tracks"
                  value={options.min_unavailable}
                  max={20}
                  disabled={disabled}
                  onChange={(value) => onChange({ ...options, min_unavailable: value })}
                />
                <ThresholdField
                  label="Tracks (oversized)"
                  value={options.min_bloated_tracks}
                  min={50}
                  max={500}
                  disabled={disabled}
                  onChange={(value) => onChange({ ...options, min_bloated_tracks: value })}
                />
              </div>
            </SubBlock>

            <Field label="Minimum playlist size (tracks)">
              <input
                type="number"
                min={0}
                disabled={disabled}
                value={options.min_track_count}
                onChange={(e) =>
                  onChange({
                    ...options,
                    min_track_count: Math.max(0, Number(e.target.value) || 0),
                  })
                }
                className="w-24 rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-zinc-200"
              />
            </Field>

            <SubBlock title="Performance">
              <div className="space-y-4">
                <ToggleSwitch
                  id="use-cache"
                  checked={options.use_scan_cache}
                  disabled={disabled || options.force_rescan}
                  onChange={(checked) => onChange({ ...options, use_scan_cache: checked })}
                  label="Reuse recent scan data"
                  description="Faster when you've scanned recently. Recommended."
                />
                <ToggleSwitch
                  id="force-rescan"
                  checked={options.force_rescan}
                  disabled={disabled}
                  onChange={(checked) =>
                    onChange({
                      ...options,
                      force_rescan: checked,
                      use_scan_cache: checked ? false : options.use_scan_cache,
                    })
                  }
                  label="Always scan fresh"
                  description="Ignores saved data — slower but fully up to date."
                />
                <ToggleSwitch
                  id="conservative"
                  checked={options.conservative_scan}
                  disabled={disabled}
                  onChange={(checked) => onChange({ ...options, conservative_scan: checked })}
                  label="Go easy on Spotify"
                  description="Slower scans to avoid hitting rate limits."
                />
              </div>
            </SubBlock>

            <SubBlock title="Automatic weekly scan">
              <ToggleSwitch
                id="schedule-enabled"
                checked={scheduleEnabled}
                disabled={disabled || saveSchedule.isPending}
                onChange={setScheduleEnabled}
                label="Run on a schedule"
                description="Uses these settings. Results appear in history below."
              />
              {scheduleEnabled && (
                <div className="mt-4 space-y-3">
                  <Field label="When">
                    <select
                      value={scheduleCron}
                      disabled={disabled || saveSchedule.isPending}
                      onChange={(e) => setScheduleCron(e.target.value)}
                      className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-zinc-200"
                    >
                      {CRON_PRESETS.map((preset) => (
                        <option key={preset.value} value={preset.value}>
                          {preset.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <ToggleSwitch
                    id="schedule-email"
                    checked={scheduleNotify}
                    disabled={disabled || saveSchedule.isPending}
                    onChange={setScheduleNotify}
                    label="Email me a summary"
                    description="Requires SMTP in server config. History is always saved here."
                  />
                  <button
                    type="button"
                    disabled={disabled || saveSchedule.isPending}
                    onClick={() => saveSchedule.mutate()}
                    className="rounded-lg bg-violet-500/20 px-4 py-2 text-sm text-violet-200"
                  >
                    {saveSchedule.isPending ? "Saving…" : "Save schedule"}
                  </button>
                  {schedule.data?.last_run_summary && (
                    <p className="text-xs text-zinc-500">
                      Last run: {schedule.data.last_run_summary}
                    </p>
                  )}
                  {scheduleRuns.data && scheduleRuns.data.length > 0 && (
                    <ul className="max-h-32 space-y-1.5 overflow-y-auto text-xs text-zinc-500">
                      {scheduleRuns.data.map((run) => (
                        <li key={run.id} className="rounded-lg bg-white/[0.03] px-2 py-1.5">
                          {run.started_at.slice(0, 10)} ·{" "}
                          <span
                            className={
                              run.status === "completed" ? "text-emerald-400" : "text-red-300"
                            }
                          >
                            {run.status}
                          </span>
                          {run.summary && ` — ${run.summary}`}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </SubBlock>
          </div>
        )}
      </section>
    </div>
  );
}

function ConfigSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-white/10 bg-black/20 p-4">
      <h4 className="text-sm font-medium text-zinc-100">{title}</h4>
      <p className="mt-1 text-xs text-zinc-500">{description}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function SubBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">{title}</p>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="mb-1.5 block text-xs text-zinc-400">{label}</label>
      {children}
    </div>
  );
}

function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
  disabled,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string }[];
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex rounded-xl border border-white/10 bg-black/40 p-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          disabled={disabled}
          onClick={() => onChange(option.value)}
          className={`rounded-lg px-4 py-2 text-sm transition ${
            value === option.value
              ? "bg-violet-500/25 text-violet-100 shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function ThresholdField({
  label,
  value,
  min = 0,
  max,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  min?: number;
  max: number;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <div className="rounded-lg bg-white/[0.03] px-3 py-2">
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-zinc-400">{label}</span>
        <span className="text-sm font-medium text-zinc-200">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        disabled={disabled}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 w-full accent-violet-500"
      />
    </div>
  );
}

function PlaylistPicker({
  filter,
  onFilterChange,
  playlists,
  selectedIds,
  minTrackCount,
  disabled,
  onToggle,
  onSelectVisible,
  onClear,
}: {
  filter: string;
  onFilterChange: (value: string) => void;
  playlists: PlaylistSummary[];
  selectedIds: string[];
  minTrackCount: number;
  disabled?: boolean;
  onToggle: (playlistId: string) => void;
  onSelectVisible: () => void;
  onClear: () => void;
}) {
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={filter}
          onChange={(e) => onFilterChange(e.target.value)}
          placeholder="Search playlists…"
          disabled={disabled}
          className="min-w-[10rem] flex-1 rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm"
        />
        <button
          type="button"
          disabled={disabled}
          onClick={onSelectVisible}
          className="text-xs text-violet-300 hover:underline"
        >
          All visible
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={onClear}
          className="text-xs text-zinc-500 hover:underline"
        >
          Clear
        </button>
      </div>
      <ul className="max-h-44 space-y-1 overflow-y-auto">
        {playlists.length === 0 && (
          <li className="py-4 text-center text-sm text-zinc-500">No playlists match.</li>
        )}
        {playlists.map((playlist) => {
          const selected = selectedIds.includes(playlist.id);
          const tooSmall = minTrackCount > 0 && playlist.track_count < minTrackCount;
          return (
            <li key={playlist.id}>
              <button
                type="button"
                disabled={disabled || tooSmall}
                onClick={() => onToggle(playlist.id)}
                className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition ${
                  selected
                    ? "border-violet-400/40 bg-violet-500/10"
                    : "border-transparent bg-white/[0.02] hover:bg-white/[0.05]"
                } ${tooSmall ? "opacity-40" : ""}`}
              >
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs ${
                    selected
                      ? "bg-violet-500 text-black"
                      : "border border-white/20 text-transparent"
                  }`}
                >
                  ✓
                </span>
                <span className="min-w-0 flex-1 truncate text-sm text-zinc-200">
                  {playlist.name}
                </span>
                <span className="shrink-0 text-xs text-zinc-500">
                  {playlist.track_count} tracks
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
