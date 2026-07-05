# Spotify Curator

Self-hosted Spotify playlist management tool with cleanup, mood-based curation,
and auto-discovery.

## Features

- **Cleanup** — remove duplicates, unavailable tracks, skip-heavy songs; split
  by mood clusters
- **Curate (Mood Concierge)** — conversational interview to build playlists for
  your current vibe
- **Discover** — weekly or on-demand playlists from recommendations + AI taste scoring
- **AI Engine** — provider-agnostic layer (Anthropic/OpenAI/Cursor, API or CLI
  transport)

## Prerequisites

1. Spotify Developer app — **HTTPS redirect URI required** (Spotify rejects `http://`)
2. Python 3.13+ and [uv](https://docs.astral.sh/uv/)
3. Node.js 20+
4. [mkcert](https://github.com/FiloSottile/mkcert) for local HTTPS
   (`brew install mkcert`)
5. Global [lintro](https://github.com/lgtm-hq/py-lintro) for lint/review
   (`uv tool install lintro`)

## Spotify Redirect URI

Spotify no longer accepts insecure (`http://`) redirect URIs. For local
development, use:

```text
https://localhost:8000/auth/callback
```

Add that in your
[Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
under **Redirect URIs**.

## Setup

### Backend

```bash
cd spotify-curator
uv sync --group dev
cp backend/.env.example backend/.env
# Fill in SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SECRET_KEY, and AI keys

# One-time: generate trusted local TLS certs
chmod +x backend/scripts/dev-certs.sh backend/scripts/run-dev.sh
./backend/scripts/dev-certs.sh

# Run backend over HTTPS
./backend/scripts/run-dev.sh
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173> and click **Connect Spotify**.

## Development

```bash
# Sync dev tools (ruff, mypy, bandit, …) into .venv
uv sync --group dev

# Format and lint — use global lintro with project .venv on PATH
# (install: uv tool install lintro)
export PATH="$(pwd)/.venv/bin:$PATH"
lintro fmt
lintro chk   # must pass with 0 issues

# Type-check
uv run mypy backend/app

# AI diff review (global lintro; requires ai.enabled in .lintro-config.yaml)
lintro review --uncommitted
```

## Configuration

- `backend/.env` — Spotify credentials and secrets
- `backend/config.yaml` — AI provider settings (`provider`, `transport`, `model`)

Set `SPOTIFY_REDIRECT_URI` in `.env` to match exactly what you registered in
the Spotify dashboard.

## API Overview

| Endpoint | Description |
| -------- | ----------- |
| `GET /auth/login` | Start Spotify OAuth |
| `GET /playlists` | List playlists |
| `POST /cleanup/analyze/{id}` | Analyze playlist |
| `POST /curate/start` | Start mood interview |
| `POST /discover/generate` | Generate discovery playlist |
