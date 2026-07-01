import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/cleanup", label: "Cleanup" },
  { to: "/curate", label: "Curate" },
  { to: "/discover", label: "Discover" },
];

export function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });

  const logout = useMutation({
    mutationFn: () => api.logout(),
    onSuccess: async () => {
      await queryClient.resetQueries();
      navigate("/");
    },
  });

  return (
    <div className="min-h-screen">
      <header className="border-b border-white/10 bg-black/40 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-semibold text-emerald-400">Spotify Curator</h1>
            <p className="text-sm text-zinc-400">Cleanup, curate, and discover music</p>
          </div>
          <nav className="flex items-center gap-2">
            {nav.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={`rounded-lg px-3 py-2 text-sm ${
                  location.pathname === item.to
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "text-zinc-300 hover:bg-white/5"
                }`}
              >
                {item.label}
              </Link>
            ))}

            {me.isLoading && (
              <div className="h-9 w-28 animate-pulse rounded-lg bg-white/10" />
            )}

            {me.isSuccess && me.data.connected && (
              <div className="ml-2 flex items-center gap-2 border-l border-white/10 pl-2">
                <Link
                  to="/account"
                  className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition hover:bg-white/5 ${
                    location.pathname === "/account"
                      ? "bg-emerald-500/20 text-emerald-300"
                      : "text-zinc-200"
                  }`}
                >
                  {me.data.image_url ? (
                    <img
                      src={me.data.image_url}
                      alt=""
                      className="h-8 w-8 rounded-full object-cover"
                    />
                  ) : (
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20 text-xs text-emerald-300">
                      {(me.data.display_name ?? "?").slice(0, 1).toUpperCase()}
                    </div>
                  )}
                  <span className="max-w-[8rem] truncate">
                    {me.data.display_name ?? "Account"}
                  </span>
                </Link>
                <button
                  type="button"
                  disabled={logout.isPending}
                  onClick={() => logout.mutate()}
                  className="rounded-lg border border-white/10 px-3 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-50"
                >
                  Log out
                </button>
              </div>
            )}

            {me.isError && (
              <button
                type="button"
                onClick={() => api.login()}
                className="rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-black hover:bg-emerald-400"
              >
                Connect Spotify
              </button>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
