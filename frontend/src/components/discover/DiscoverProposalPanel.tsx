import { Link } from "react-router-dom";
import type { DiscoverProposal } from "../../api/client";
import { DiscoverReasoning } from "./DiscoverReasoning";
import { PlaylistPreview } from "../PlaylistPreview";
import { UserFacingError } from "../UserFacingError";

function statusBadgeClass(status: DiscoverProposal["status"]): string {
  if (status === "saved") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
  }
  if (status === "dismissed") {
    return "border-zinc-500/30 bg-zinc-500/10 text-zinc-400";
  }
  return "border-sky-500/30 bg-sky-500/10 text-sky-200";
}

function statusLabel(status: DiscoverProposal["status"]): string {
  if (status === "saved") {
    return "On Spotify";
  }
  if (status === "dismissed") {
    return "Dismissed";
  }
  return "Pending review";
}

function spotifyPlaylistUrl(playlistId: string): string {
  return `https://open.spotify.com/playlist/${playlistId}`;
}

export function DiscoverProposalPanel({
  proposal,
  tracks,
  loading,
  isSaving,
  saveError,
  rateLimited,
  onRemoveTrack,
  onSave,
}: {
  proposal: DiscoverProposal;
  tracks: DiscoverProposal["tracks"];
  loading: boolean;
  isSaving: boolean;
  saveError: string | null;
  rateLimited: boolean;
  onRemoveTrack: (trackId: string) => void;
  onSave: () => void;
}) {
  const isPending = proposal.status === "pending";
  const isSaved = proposal.status === "saved" && Boolean(proposal.playlist_id);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-sm text-zinc-500">
        Loading proposal…
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-xl font-semibold">{proposal.name}</h3>
              <span
                className={`rounded-full border px-2.5 py-0.5 text-xs ${statusBadgeClass(proposal.status)}`}
              >
                {statusLabel(proposal.status)}
              </span>
            </div>
            {proposal.description && (
              <p className="max-w-2xl text-sm text-zinc-400">{proposal.description}</p>
            )}
            <p className="text-sm text-zinc-500">
              {tracks.length} track{tracks.length === 1 ? "" : "s"}
              {isPending ? " · review below, then save to Spotify" : ""}
            </p>
          </div>
          {isSaved && proposal.playlist_id && (
            <div className="flex flex-wrap gap-2">
              <Link
                to={`/playlists/${proposal.playlist_id}`}
                className="rounded-lg border border-emerald-400/40 px-4 py-2 text-sm text-emerald-200 hover:bg-emerald-500/10"
              >
                Open in app
              </Link>
              <a
                href={spotifyPlaylistUrl(proposal.playlist_id)}
                target="_blank"
                rel="noreferrer"
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5"
              >
                Open in Spotify
              </a>
            </div>
          )}
        </div>

        <DiscoverReasoning reasoning={proposal.reasoning} rationale={proposal.rationale} />

        <PlaylistPreview tracks={tracks} onRemove={onRemoveTrack} readOnly={!isPending} />

        {saveError && <UserFacingError compact title="Save failed" error={saveError} />}

        {isPending && (
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              disabled={isSaving || tracks.length === 0 || rateLimited}
              onClick={onSave}
              className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black transition hover:bg-emerald-400 disabled:opacity-60"
            >
              {isSaving ? "Saving to Spotify…" : `Save ${tracks.length} tracks to Spotify`}
            </button>
            <p className="self-center text-xs text-zinc-500">
              Creates a private playlist in your library. Remove tracks above before saving.
            </p>
          </div>
        )}

        {isSaved && (
          <p className="text-sm text-emerald-300">
            Saved to Spotify
            {proposal.playlist_id ? ` · playlist ID ${proposal.playlist_id}` : ""}
          </p>
        )}
      </div>
    </div>
  );
}

export function DiscoverProposalPlaceholder() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
      <p className="text-zinc-400">Select a run to review</p>
      <p className="text-sm text-zinc-500">
        Choose a recent run on the left, or generate a new proposal.
      </p>
    </div>
  );
}
