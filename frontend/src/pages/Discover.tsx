import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function Discover() {
  const history = useQuery({
    queryKey: ["discover-history"],
    queryFn: api.discoverHistory,
  });

  const generate = useMutation({
    mutationFn: api.discoverGenerate,
    onSuccess: () => history.refetch(),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Discover</h2>
          <p className="text-zinc-400">
            Auto-generate a playlist of new tracks that fit your taste.
          </p>
        </div>
        <button
          type="button"
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
          className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black disabled:opacity-50"
        >
          {generate.isPending ? "Generating..." : "Generate now"}
        </button>
      </div>

      {generate.data && (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-6">
          <h3 className="text-xl font-semibold">{generate.data.name}</h3>
          <p className="text-sm text-zinc-400">
            {generate.data.track_count} tracks · Playlist ID: {generate.data.playlist_id}
          </p>
          <p className="mt-2 text-zinc-300">{generate.data.reasoning}</p>
        </div>
      )}

      <section>
        <h3 className="mb-3 text-lg font-medium">History</h3>
        <div className="space-y-2">
          {(history.data ?? []).map((run) => (
            <div
              key={run.run_id}
              className="rounded-lg border border-white/10 bg-white/5 px-4 py-3"
            >
              <p className="font-medium">{run.name}</p>
              <p className="text-sm text-zinc-400">{new Date(run.created_at).toLocaleString()}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
