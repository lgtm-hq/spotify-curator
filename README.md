# Spotify Curator

Self-hosted Spotify playlist management tool with cleanup, mood-based curation, and auto-discovery.

## Features

- **Cleanup** — remove duplicates, unavailable tracks, skip-heavy songs; split by mood clusters
- **Curate (Mood Concierge)** — conversational interview to build playlists for your current vibe
- **Discover** — weekly or on-demand playlists from recommendations + AI taste scoring
- **AI Engine** — provider-agnostic layer (Anthropic/OpenAI/Cursor, API or CLI transport)

## Prerequisites

1. Spotify Developer app with redirect URI: `http://localhost:8000/auth/callback`
2. Python 3.11+
3. Node.js 20+

## Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and AI keys
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and click **Connect Spotify**.

## Configuration

Edit `backend/config.yaml` for AI provider settings:

```yaml
ai:
  enabled: true
  provider: anthropic
  transport: api
  model: claude-sonnet-4-20250514
```

## API Overview

| Endpoint | Description |
|----------|-------------|
| `GET /auth/login` | Start Spotify OAuth |
| `GET /playlists` | List playlists |
| `POST /cleanup/analyze/{id}` | Analyze playlist |
| `POST /curate/start` | Start mood interview |
| `POST /discover/generate` | Generate discovery playlist |
