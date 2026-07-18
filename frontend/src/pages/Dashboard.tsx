import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { PlaylistBrowser } from "../components/playlists/PlaylistBrowser";
import { TasteProfileDisplay, TasteProfileSkeleton } from "../components/taste/TasteProfileDisplay";
import { api } from "../api/client";

function isAuthRequiredError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  return (
    message.includes("not authenticated") ||
    message.includes("401") ||
    message.includes("spotify not connected")
  );
}

export function Dashboard() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const justLoggedIn = searchParams.get("login") === "1";

  const auth = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });
  const taste = useQuery({
    queryKey: ["taste"],
    queryFn: () => api.taste(false),
    enabled: auth.isSuccess,
    refetchInterval: (query) => {
      if (!justLoggedIn || query.state.data) {
        return false;
      }
      return 3000;
    },
  });

  const refreshTaste = useMutation({
    mutationFn: () => api.tasteRefresh(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["taste"] });
      await queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });

  useEffect(() => {
    if (justLoggedIn && taste.data && auth.data?.has_taste_profile) {
      searchParams.delete("login");
      setSearchParams(searchParams, { replace: true });
    }
  }, [justLoggedIn, taste.data, auth.data?.has_taste_profile, searchParams, setSearchParams]);

  if (auth.isLoading) {
    return <p className="text-zinc-400">Loading…</p>;
  }

  if (auth.isError) {
    if (isAuthRequiredError(auth.error)) {
      return (
        <div className="rounded-xl border border-white/10 bg-white/5 p-8 text-center">
          <h2 className="mb-2 text-2xl font-semibold">Welcome</h2>
          <p className="mb-6 text-zinc-400">Connect your Spotify account to get started.</p>
          <button
            type="button"
            onClick={() => api.login()}
            className="rounded-lg bg-emerald-500 px-6 py-3 font-medium text-black"
          >
            Connect Spotify
          </button>
          <p className="mt-4 text-xs text-zinc-500">
            First time?{" "}
            <a
              href="https://github.com/lgtm-hq/spotify-curator/blob/main/docs/spotify-app-setup.md"
              target="_blank"
              rel="noreferrer"
              className="text-emerald-400 hover:underline"
            >
              Set up your Spotify Developer app
            </a>
          </p>
        </div>
      );
    }

    const message =
      auth.error instanceof Error ? auth.error.message : "Could not reach the server.";
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center">
        <h2 className="mb-2 text-xl font-semibold text-red-200">Connection problem</h2>
        <p className="mb-6 text-sm text-zinc-400">{message}</p>
        <button
          type="button"
          onClick={() => void queryClient.invalidateQueries({ queryKey: ["me"] })}
          className="rounded-lg bg-emerald-500 px-6 py-3 font-medium text-black"
        >
          Retry
        </button>
      </div>
    );
  }

  const tasteLoading = taste.isLoading || (justLoggedIn && !taste.data && !taste.isError);

  return (
    <div className="space-y-8">
      {justLoggedIn && tasteLoading && (
        <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 px-4 py-3 text-sm text-violet-200">
          Building your taste profile from Spotify listening data…
        </div>
      )}

      <section>
        <PlaylistBrowser />
      </section>

      <section className="rounded-xl border border-white/10 bg-white/5 p-6">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="text-xl font-semibold">Taste Profile</h2>
          <button
            type="button"
            disabled={refreshTaste.isPending || tasteLoading}
            onClick={() => refreshTaste.mutate()}
            className="text-sm text-emerald-400 hover:underline disabled:opacity-50"
          >
            {refreshTaste.isPending ? "Regenerating…" : "Regenerate"}
          </button>
        </div>

        {tasteLoading && <TasteProfileSkeleton />}

        {taste.isError && (
          <p className="text-sm text-red-300">
            Could not load taste profile. Try regenerating from the Account page.
          </p>
        )}

        {taste.data && !tasteLoading && <TasteProfileDisplay profile={taste.data} />}

        {!taste.data && !tasteLoading && !taste.isError && (
          <p className="text-sm text-zinc-400">
            No taste profile yet. Visit Account to generate one.
          </p>
        )}
      </section>
    </div>
  );
}
