import { Link, Outlet, useLocation } from "react-router-dom";
import { api } from "../api/client";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/cleanup", label: "Cleanup" },
  { to: "/curate", label: "Curate" },
  { to: "/discover", label: "Discover" },
];

export function Layout() {
  const location = useLocation();

  return (
    <div className="min-h-screen">
      <header className="border-b border-white/10 bg-black/40 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-semibold text-emerald-400">Spotify Curator</h1>
            <p className="text-sm text-zinc-400">Cleanup, curate, and discover music</p>
          </div>
          <nav className="flex gap-2">
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
            <button
              type="button"
              onClick={() => api.login()}
              className="rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-black hover:bg-emerald-400"
            >
              Connect Spotify
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
