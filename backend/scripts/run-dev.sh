#!/usr/bin/env bash
# Run the backend over HTTPS (required by Spotify redirect URI policy).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="$ROOT/certs"

if [[ ! -f "$CERT_DIR/cert.pem" || ! -f "$CERT_DIR/key.pem" ]]; then
  echo "Missing TLS certs. Run: ./scripts/dev-certs.sh"
  exit 1
fi

cd "$ROOT"
source .venv/bin/activate
uvicorn app.main:app \
  --reload \
  --host 127.0.0.1 \
  --port 8000 \
  --ssl-keyfile "$CERT_DIR/key.pem" \
  --ssl-certfile "$CERT_DIR/cert.pem"
