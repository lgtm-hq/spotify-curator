# AGENTS.md

## Cursor Cloud specific instructions

Spotify Curator is two services in one repo:

- `backend/` — FastAPI app (`app.main:app`), managed with `uv` (Python 3.13+; uv resolves 3.14 which satisfies this). SQLite DB auto-created on startup; no migrations to run.
- `frontend/` — React 19 + Vite SPA, managed with `npm` (README says `npm install`; a `bun.lock` also exists but the npm workflow is canonical). Vite dev server proxies API routes to the backend.

### Running the services

- Backend: `./backend/scripts/run-dev.sh` (serves HTTPS on `https://127.0.0.1:8000` with `--reload`). It requires `backend/.env` and TLS certs at `backend/certs/{cert.pem,key.pem}`, and sources `backend/.env` as shell vars.
- Frontend: `npm run dev` in `frontend/` (serves `http://127.0.0.1:5173`). Open this URL and click **Connect Spotify**.
- The Vite proxy targets `https://127.0.0.1:8000` with `secure: false`, so a self-signed backend cert is fine — the cert does not need to be trusted.

### Non-obvious setup caveats

- `mkcert` (what `backend/scripts/dev-certs.sh` expects) is not available in this environment. Generate self-signed certs directly instead: `openssl req -x509 -newkey rsa:2048 -nodes -keyout backend/certs/key.pem -out backend/certs/cert.pem -days 825 -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"`. `run-dev.sh` only checks that the two PEM files exist.
- `backend/.env` (gitignored) must exist; copy from `backend/.env.example` and set a random `SECRET_KEY`. Both `.env` and `backend/certs/*` are one-off local artifacts (not in git, not in the update script).
- Spotify OAuth and AI features need real credentials that are NOT set by default: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and an AI key (`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`CURSOR_API_KEY`). Without them the app runs and the **Connect Spotify** button reaches Spotify's login page, but authenticated flows (playlists, cleanup, curate, discover) cannot complete.
- `backend/config.yaml` sets AI `transport: cli` by default, which spawns a provider CLI subprocess per message. Switch to `transport: api` (and provide an API key) for API-based AI.

### Lint / test / build

- Backend lint/format: `uv run ruff check backend`, `uv run ruff format --check backend`, `uv run mypy backend/app`. The README's `lintro` wrapper is optional (needs a global `lintro` tool). Note: prototype code currently has a couple of pre-existing `ruff` E501/format findings in `backend/app/playlists/cache.py`.
- Frontend lint: `npm run lint` (oxlint). Frontend build: `npm run build` (`tsc -b && vite build`).
- Backend tests: `uv run pytest`. `testpaths` points at `backend/tests`, which does not exist yet, so pytest currently collects 0 tests.
