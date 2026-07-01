# Spotify Curator

Self-hosted Spotify playlist management tool with cleanup, mood-based curation, and auto-discovery.

## Features

- **Cleanup** — remove duplicates, unavailable tracks, skip-heavy songs; split by mood clusters
- **Curate (Mood Concierge)** — conversational interview to build playlists for your current vibe
- **Discover** — weekly or on-demand playlists from recommendations + AI taste scoring
- **AI Engine** — provider-agnostic layer (Anthropic/OpenAI/Cursor, API or CLI transport)

## Prerequisites

1. Spotify Developer app — **HTTPS redirect URI required** (Spotify rejects `http://`)
2. Python 3.11+
3. Node.js 20+
4. [mkcert](https://github.com/FiloSottile/mkcert) for local HTTPS (`brew install mkcert`)

## Spotify Redirect URI

Spotify no longer accepts insecure (`http://`) redirect URIs. For local development, use:

```
https://127.0.0.1:8000/auth/callback
```

Add that in your [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) under **Redirect URIs**.

If you deploy to production, also add:

```
https://127.0.0.1/auth/callback
```

## Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and AI keys

# One-time: generate trusted local TLS certs
chmod +x scripts/dev-certs.sh scripts/run-dev.sh
./scripts/dev-certs.sh

# Run backend over HTTPS
./scripts/run-dev.sh
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and click **Connect Spotify**.

The Vite dev server proxies API calls to `https://127.0.0.1:8000` (self-signed certs are accepted in dev).

## Configuration

Edit `backend/config.yaml` for AI provider settings:

```yaml
ai:
  enabled: true
  provider: anthropic
  transport: api
  model: claude-sonnet-4-20250514
```

Set `SPOTIFY_REDIRECT_URI` in `.env` to match exactly what you registered in the Spotify dashboard.

## API Overview

| Endpoint | Description |
|----------|-------------|
| `GET /auth/login` | Start Spotify OAuth |
| `GET /playlists` | List playlists |
| `POST /cleanup/analyze/{id}` | Analyze playlist |
| `POST /curate/start` | Start mood interview |
| `POST /discover/generate` | Generate discovery playlist |
