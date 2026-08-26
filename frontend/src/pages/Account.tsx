import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { TasteProfileDisplay, TasteProfileSkeleton } from "../components/taste/TasteProfileDisplay";

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "Never";
  }
  return new Date(value).toLocaleString();
}

export function Account() {
  const queryClient = useQueryClient();
  const account = useQuery({ queryKey: ["account"], queryFn: api.account, retry: false });
  const taste = useQuery({
    queryKey: ["taste"],
    queryFn: () => api.taste(false),
    enabled: account.isSuccess && account.data.has_taste_profile,
  });

  const regenerateTaste = useMutation({
    mutationFn: () => api.tasteRefresh(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["taste"] });
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      await queryClient.invalidateQueries({ queryKey: ["account"] });
    },
  });

  const generateTaste = useMutation({
    mutationFn: () => api.taste(false),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["taste"] });
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      await queryClient.invalidateQueries({ queryKey: ["account"] });
    },
  });

  const logout = useMutation({
    mutationFn: () => api.logout(),
    onSuccess: () => {
      window.location.href = "/";
    },
  });

  if (account.isError) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/5 p-8 text-center">
        <h2 className="mb-2 text-2xl font-semibold">Account</h2>
        <p className="mb-6 text-zinc-400">Connect Spotify to view your account dashboard.</p>
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

  if (account.isLoading) {
    return <p className="text-zinc-400">Loading account…</p>;
  }

  const user = account.data?.user;
  const isTasteBusy = generateTaste.isPending || regenerateTaste.isPending;

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-white/10 bg-white/5 p-6">
        <h2 className="mb-4 text-2xl font-semibold">Account</h2>
        {user ? (
          <div className="flex flex-wrap items-center gap-4">
            {user.image_url ? (
              <img src={user.image_url} alt="" className="h-20 w-20 rounded-full object-cover" />
            ) : (
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-emerald-500/20 text-2xl text-emerald-300">
                {user.display_name.slice(0, 1).toUpperCase()}
              </div>
            )}
            <div>
              <p className="text-xl font-medium">{user.display_name}</p>
              {user.email && <p className="text-sm text-zinc-400">{user.email}</p>}
              <p className="mt-1 text-sm text-zinc-500">
                Connected {formatDate(user.connected_at)}
                {user.product ? ` · ${user.product}` : ""}
              </p>
            </div>
          </div>
        ) : (
          <p className="text-zinc-400">Profile details will appear after reconnecting.</p>
        )}
      </section>

      <section className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-6">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="text-xl font-semibold text-violet-200">Taste profile</h3>
            <p className="mt-1 max-w-2xl text-sm text-zinc-400">
              AI analysis of your top artists, tracks, and listening patterns. Used by Curate,
              Cleanup suggestions, and Discover.
            </p>
            <p className="mt-2 text-xs text-zinc-500">
              Last updated: {formatDate(account.data?.taste_updated_at)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!account.data?.has_taste_profile ? (
              <button
                type="button"
                disabled={isTasteBusy}
                onClick={() => generateTaste.mutate()}
                className="rounded-lg bg-violet-500 px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
              >
                {isTasteBusy ? "Generating…" : "Generate taste profile"}
              </button>
            ) : (
              <button
                type="button"
                disabled={isTasteBusy}
                onClick={() => regenerateTaste.mutate()}
                className="rounded-lg border border-violet-500/40 px-4 py-2 text-sm text-violet-300 disabled:opacity-50"
              >
                {isTasteBusy ? "Regenerating…" : "Regenerate taste profile"}
              </button>
            )}
          </div>
        </div>

        {(generateTaste.isError || regenerateTaste.isError) && (
          <p className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {(generateTaste.error ?? regenerateTaste.error) instanceof Error
              ? (generateTaste.error ?? regenerateTaste.error)?.message
              : "Could not update taste profile."}
          </p>
        )}

        {isTasteBusy && <TasteProfileSkeleton />}

        {!isTasteBusy && taste.data && <TasteProfileDisplay profile={taste.data} />}

        {!isTasteBusy && !taste.data && !account.data?.has_taste_profile && (
          <p className="text-sm text-zinc-400">
            No taste profile yet. Generate one to power AI features across the app.
          </p>
        )}
      </section>

      <section className="rounded-xl border border-white/10 bg-white/5 p-6">
        <h3 className="mb-2 text-xl font-semibold">How your data is stored</h3>
        <p className="mb-4 text-sm text-zinc-400">{account.data?.data_storage.description}</p>
        <p className="mb-3 text-xs uppercase tracking-wide text-zinc-500">
          Database: {account.data?.data_storage.database}
        </p>
        <ul className="space-y-2">
          {account.data?.data_storage.stored_data.map((item) => (
            <li
              key={item.key}
              className="rounded-lg border border-white/5 bg-black/20 px-4 py-3 text-sm"
            >
              <span className="font-medium text-zinc-200">{item.key}</span>
              <span className="text-zinc-400"> — {item.description}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-red-500/20 bg-red-500/5 p-6">
        <h3 className="mb-2 text-lg font-medium text-red-200">Switch account</h3>
        <p className="mb-4 text-sm text-zinc-400">
          Logging out clears your Spotify tokens and taste profile from this app so another account
          can connect.
        </p>
        <button
          type="button"
          disabled={logout.isPending}
          onClick={() => logout.mutate()}
          className="rounded-lg border border-red-500/40 px-4 py-2 text-sm text-red-300 hover:bg-red-500/10 disabled:opacity-50"
        >
          {logout.isPending ? "Logging out…" : "Log out"}
        </button>
      </section>
    </div>
  );
}
