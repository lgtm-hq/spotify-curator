import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useBackgroundActivity } from "../contexts/backgroundActivity";
import { SpotifyRateLimitBanner } from "./SpotifyRateLimitBanner";
import { useSpotifyUsage } from "../hooks/useSpotifyUsage";

const nav = [
  { to: "/", label: "Dashboard", exact: true },
  { to: "/cleanup", label: "AI Advisor" },
  { to: "/curate", label: "Curate" },
  { to: "/discover", label: "Discover" },
];

function isNavActive(pathname: string, to: string, exact?: boolean): boolean {
  if (exact) {
    return pathname === to;
  }
  return pathname === to || pathname.startsWith(`${to}/`);
}

function NavActivityDot({ className }: { className: string }) {
  return <span aria-hidden className={`ml-1.5 inline-block h-2 w-2 rounded-full ${className}`} />;
}

function NavActivityIndicator({ busy, complete }: { busy: boolean; complete: boolean }) {
  if (busy) {
    return <NavActivityDot className="animate-pulse bg-violet-400" />;
  }
  if (complete) {
    return <NavActivityDot className="bg-emerald-400" />;
  }
  return null;
}

export function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { dashboard, advisor, curate, discover } = useBackgroundActivity();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });
  const { usage, rateLimited, onLimitExpired } = useSpotifyUsage({
    enabled: me.data?.connected ?? false,
  });
  const showGlobalRateLimitBanner = rateLimited && Boolean(usage);

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
            <p className="text-sm text-zinc-400">Curate, clean up, and discover music</p>
          </div>
          <nav className="flex items-center gap-2">
            {nav.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={`inline-flex items-center rounded-lg px-3 py-2 text-sm ${
                  isNavActive(location.pathname, item.to, item.exact)
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "text-zinc-300 hover:bg-white/5"
                }`}
              >
                {item.label}
                {item.to === "/" && (
                  <NavActivityIndicator busy={dashboard.scanning} complete={dashboard.hasResults} />
                )}
                {item.to === "/cleanup" && (
                  <NavActivityIndicator busy={advisor.scanning} complete={advisor.hasResults} />
                )}
                {item.to === "/curate" && (
                  <NavActivityIndicator busy={curate.busy} complete={curate.hasResults} />
                )}
                {item.to === "/discover" && (
                  <NavActivityIndicator busy={discover.busy} complete={discover.hasResults} />
                )}
              </Link>
            ))}

            {me.isLoading && <div className="h-9 w-28 animate-pulse rounded-lg bg-white/10" />}

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
                  <span className="max-w-[8rem] truncate">{me.data.display_name ?? "Account"}</span>
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
        {showGlobalRateLimitBanner && usage && (
          <div className="border-t border-red-500/20 bg-red-950/40">
            <div className="mx-auto max-w-6xl px-6 py-3">
              <SpotifyRateLimitBanner usage={usage} onLimitExpired={onLimitExpired} />
            </div>
          </div>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
