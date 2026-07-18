# Deployment Guide

This guide covers three deployment scenarios:

1. **[Local development](#local-development)** — HTTPS backend + Vite dev server
2. **[Docker (Dockerfile-based)](#docker-dockerfile-based)** — single container;\
   add your own reverse proxy for TLS
3. **[Docker Compose with Caddy TLS](#docker-compose-with-caddy-tls)** — arriving in
   [#18][issue-18]; intended flow described below

---

## Environment Variables

All variables are read from `backend/.env` (local dev) or an env file passed to Docker.

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `SPOTIFY_CLIENT_ID` | Yes | — | From [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) |
| `SPOTIFY_CLIENT_SECRET` | Yes | — | From Spotify Developer Dashboard |
| `SPOTIFY_REDIRECT_URI` | Yes | `https://localhost:8000/auth/callback` | Must match Spotify app settings exactly |
| `SECRET_KEY` | Yes | — | Long random string; used for session signing |
| `DATABASE_URL` | No | `sqlite:////data/spotify_curator.db` (container) / `sqlite:///./spotify_curator.db` (local) | SQLite path; set automatically in the container |
| `FRONTEND_URL` | No | `http://localhost:5173` | CORS allow-origin; set to your public hostname in production |
| `ANTHROPIC_API_KEY` | AI only | — | Required when `config.yaml` provider is `anthropic` and transport is `api` |
| `OPENAI_API_KEY` | AI only | — | Required when provider is `openai` and transport is `api` |
| `CURSOR_API_KEY` | AI only | — | Required when provider is `cursor` and transport is `api` |

> **AI transport note:** `backend/config.yaml` defaults to `transport: cli`, which
> spawns a provider CLI subprocess per request. CLI transport **cannot work inside a
> container** (the CLI binary is not installed). Set `transport: api` and supply the
> corresponding API key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `CURSOR_API_KEY`)
> whenever running as a container.

---

## Local Development

### Prerequisites

- Python 3.13+ and [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+ and `npm`
- A Spotify Developer app — add `https://localhost:8000/auth/callback` as a Redirect URI

### 1. Clone and install

```bash
git clone https://github.com/lgtm-hq/spotify-curator.git
cd spotify-curator
uv sync
cd frontend && npm install && cd ..
```

### 2. Create the backend env file

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set at minimum:

```dotenv
SPOTIFY_CLIENT_ID=<your-client-id>
SPOTIFY_CLIENT_SECRET=<your-client-secret>
SECRET_KEY=<long-random-string>
```

### 3. Generate TLS certificates

Spotify OAuth requires an HTTPS redirect URI. The backend dev server serves HTTPS
on port 8000, so certs are needed locally.

**With `mkcert` (trusted in browser):**

```bash
./backend/scripts/dev-certs.sh
```

**Without `mkcert` (self-signed, fine for development):**

```bash
mkdir -p backend/certs
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout backend/certs/key.pem \
  -out backend/certs/cert.pem \
  -days 825 -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

The Vite proxy uses `secure: false`, so a self-signed cert works fine for local dev.

### 4. Configure AI transport (optional)

Edit `backend/config.yaml`. To use API-based AI instead of CLI:

```yaml
ai:
  provider: anthropic   # or openai / cursor
  transport: api
  model: claude-sonnet-4-20250514
```

Then set the matching key in `backend/.env` (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
or `CURSOR_API_KEY`).

### 5. Start the services

In two terminals:

```bash
# Terminal 1 — backend (HTTPS on https://127.0.0.1:8000)
./backend/scripts/run-dev.sh

# Terminal 2 — frontend (http://127.0.0.1:5173)
cd frontend
npm run dev
```

Open <http://127.0.0.1:5173> and click **Connect Spotify**.

---

## Docker (Dockerfile-based)

The repository ships a multi-stage `Dockerfile` that builds the React SPA and
packages it alongside the FastAPI backend into a single image. The container
serves the compiled frontend as static files from uvicorn — no Vite, no Node at
runtime.

### Build the image

```bash
docker build -t spotify-curator:latest .
```

To pin the version label at build time:

```bash
docker build \
  --build-arg APP_VERSION=1.0.0 \
  --build-arg VCS_REF=$(git rev-parse --short HEAD) \
  -t spotify-curator:1.0.0 .
```

### Create a data volume and env file

```bash
docker volume create spotify-curator-data

# Copy and edit your env file — the container reads DATABASE_URL from its own
# default env; you only need to override the variables below.
cp backend/.env.example .env.prod
```

Edit `.env.prod` and set at minimum:

```dotenv
SPOTIFY_CLIENT_ID=<your-client-id>
SPOTIFY_CLIENT_SECRET=<your-client-secret>
# Point redirect URI at your public hostname
SPOTIFY_REDIRECT_URI=https://example.com/auth/callback
SECRET_KEY=<long-random-string>
FRONTEND_URL=https://example.com
# AI — transport: api is required in containers (no CLI binary available)
ANTHROPIC_API_KEY=<your-key>
```

### Run the container

```bash
docker run -d \
  --name spotify-curator \
  --env-file .env.prod \
  -v spotify-curator-data:/data \
  -p 8000:8000 \
  --restart unless-stopped \
  spotify-curator:latest
```

The app listens on `http://<host>:8000`. Port 8000 is **HTTP only**; place a
TLS-terminating reverse proxy in front (Caddy, nginx, Traefik, etc.) and set
`SPOTIFY_REDIRECT_URI` / `FRONTEND_URL` to your `https://` hostname.

### Verify the container is healthy

```bash
docker ps               # STATUS should show "(healthy)" after ~15 s
docker logs spotify-curator
```

The built-in health check polls `http://127.0.0.1:8000/docs` every 30 seconds.

### Minimal Caddy reverse-proxy example

If you use Caddy as a standalone binary or system service:

```caddy
# Caddyfile
example.com {
    reverse_proxy localhost:8000
}
```

`caddy run --config Caddyfile` will automatically obtain a Let's Encrypt certificate.

---

## Docker Compose with Caddy TLS

> **Status:** compose files are not yet on this branch. They arrive in
> [#18 — feat(docker): docker-compose with optional Caddy TLS](https://github.com/lgtm-hq/spotify-curator/issues/18).
> The description below documents the intended flow; commands will be exact once
> `docker-compose.yml` lands.

Issue #18 will ship a `docker-compose.yml` with:

- An **`app`** service — runs the container image with an `./data:/data`
  volume for the SQLite database and reads credentials from a root-level `.env`
  file.
- A **`caddy`** service under a `tls` profile — a Caddy reverse proxy with a
  minimal `Caddyfile` that terminates TLS for your public domain and forwards
  requests to `app:8000`. Caddy handles Let's Encrypt certificate issuance
  automatically.

**Expected quick-start (once #18 lands):**

```text
# 1. Copy and fill in your credentials
cp .env.example .env

# 2. Start app only (HTTP, behind your own proxy)
docker compose up -d

# 3. Or start app + Caddy TLS in one command
docker compose --profile tls up -d
```

Before running with the `tls` profile, set your public domain in the `Caddyfile`
(or via an env variable) and ensure ports 80 and 443 are reachable from the
internet so Caddy can complete the ACME challenge.

---

## SQLite Backup and Restore

The SQLite database file lives at `/data/spotify_curator.db` inside the container
(mounted from the `spotify-curator-data` volume).

### WAL-safe online backup

SQLite's WAL mode requires copying both the database file and its WAL file
atomically. Use the SQLite CLI's `.backup` command:

```bash
docker exec spotify-curator \
  sqlite3 /data/spotify_curator.db ".backup /data/backup.db"
docker cp spotify-curator:/data/backup.db ./spotify_curator_$(date +%Y%m%d).db
```

Or, for a plain filesystem copy, stop writes first:

```bash
docker stop spotify-curator
docker cp spotify-curator:/data/spotify_curator.db ./spotify_curator_$(date +%Y%m%d).db
docker cp spotify-curator:/data/spotify_curator.db-wal ./spotify_curator_$(date +%Y%m%d).db-wal 2>/dev/null || true
docker start spotify-curator
```

### Continuous replication (optional)

[Litestream](https://litestream.io/) can replicate the SQLite WAL to S3, GCS, or
Azure Blob Storage in near real-time. Run it as a sidecar:

```bash
docker run -d \
  --name litestream \
  -v spotify-curator-data:/data \
  -e LITESTREAM_ACCESS_KEY_ID=<key> \
  -e LITESTREAM_SECRET_ACCESS_KEY=<secret> \
  litestream/litestream replicate \
    /data/spotify_curator.db \
    s3://your-bucket/spotify_curator.db
```

### Restore

```bash
docker stop spotify-curator
# Copy your backup into the volume
docker run --rm \
  -v spotify-curator-data:/data \
  -v $(pwd):/backup \
  busybox cp /backup/spotify_curator_<date>.db /data/spotify_curator.db
docker start spotify-curator
```

---

## Upgrade Procedure

The database schema is created (or migrated) automatically on startup; there are
no manual migration steps.

```bash
# Pull the new image
docker pull spotify-curator:latest   # or build locally: docker build -t spotify-curator:latest .

# Replace the running container (data volume is preserved)
docker stop spotify-curator && docker rm spotify-curator
docker run -d \
  --name spotify-curator \
  --env-file .env.prod \
  -v spotify-curator-data:/data \
  -p 8000:8000 \
  --restart unless-stopped \
  spotify-curator:latest
```

If you are using Docker Compose (once [#18][issue-18] lands):

```text
docker compose pull
docker compose up -d
```

[issue-18]: https://github.com/lgtm-hq/spotify-curator/issues/18
