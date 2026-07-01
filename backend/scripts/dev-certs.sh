#!/usr/bin/env bash
# Generate trusted local TLS certs for Spotify OAuth (requires mkcert).
set -euo pipefail

CERT_DIR="$(cd "$(dirname "$0")/../certs" && pwd)"

if ! command -v mkcert >/dev/null 2>&1; then
	echo "mkcert is required. Install with: brew install mkcert && mkcert -install"
	exit 1
fi

mkcert -install
mkcert -key-file "$CERT_DIR/key.pem" -cert-file "$CERT_DIR/cert.pem" \
	127.0.0.1 localhost

echo "Certs written to $CERT_DIR"
echo "Add this Redirect URI in Spotify Developer Dashboard:"
echo "  https://127.0.0.1:8000/auth/callback"
