import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function Dashboard() {
  const auth = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });
  const playlists = useQuery({
    queryKey: ["playlists"],
    queryFn: api.playlists,
    enabled: auth.isSuccess,
  });
  const taste = useQuery({
    queryKey: ["taste"],
    queryFn: () => api.taste(false),
    enabled: auth.isSuccess,
  });

  if (auth.isError) {
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
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section>
        <h2 className="mb-4 text-2xl font-semibold">Your Playlists</h2>
        {playlists.isLoading && <p className="text-zinc-400">Loading...</p>}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(playlists.data ?? []).map((playlist) => (
            <article key={playlist.id} className="rounded-xl border border-white/10 bg-white/5 p-4">
              {playlist.image_url && (
                <img
                  src={playlist.image_url}
                  alt=""
                  className="mb-3 h-32 w-full rounded-lg object-cover"
                />
              )}
              <h3 className="font-medium">{playlist.name}</h3>
              <p className="text-sm text-zinc-400">
                {playlist.track_count} tracks · {playlist.owner}
              </p>
            </article>
          ))}
        </div>
      </section>

      {taste.data && (
        <section className="rounded-xl border border-white/10 bg-white/5 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold">Taste Profile</h2>
            <button
              type="button"
              onClick={() => taste.refetch()}
              className="text-sm text-emerald-400 hover:underline"
            >
              Refresh
            </button>
          </div>
          <p className="mb-3 text-zinc-300">{taste.data.summary}</p>
          <div className="flex flex-wrap gap-2">
            {taste.data.genres.map((genre) => (
              <span
                key={genre}
                className="rounded-full bg-emerald-500/10 px-3 py-1 text-sm text-emerald-300"
              >
                {genre}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
