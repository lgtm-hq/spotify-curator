#!/usr/bin/env bash
# Run the backend over HTTPS (required by Spotify redirect URI policy).
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CERT_DIR="$PROJECT_ROOT/backend/certs"

if [[ ! -f "$CERT_DIR/cert.pem" || ! -f "$CERT_DIR/key.pem" ]]; then
	echo "Missing TLS certs. Run: ./backend/scripts/dev-certs.sh"
	exit 1
fi

cd "$PROJECT_ROOT"

# Shell-level DATABASE_URL (e.g. from other projects) overrides pydantic .env.
unset DATABASE_URL
set -a
# shellcheck source=/dev/null
source "$PROJECT_ROOT/backend/.env"
set +a

exec uv run uvicorn app.main:app \
	--reload \
	--host 127.0.0.1 \
	--port 8000 \
	--ssl-keyfile "$CERT_DIR/key.pem" \
	--ssl-certfile "$CERT_DIR/cert.pem"
