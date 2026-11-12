#!/usr/bin/env bash
set -e

# Change directory to backend parent
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "=========================================================="
echo "      OpenShorts Tailscale Dashboard & Backend Server      "
echo "=========================================================="

# Check if .env exists
if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    echo "ℹ️  Please edit .env to configure GITHUB_TOKEN if needed."
fi

# Detect Tailscale IP if available
TAILSCALE_IP=""
if command -v tailscale >/dev/null 2>&1; then
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || true)
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "📡 Host Network Details:"
if [ -n "$TAILSCALE_IP" ]; then
    echo "  ✓ Tailscale IP detected: $TAILSCALE_IP"
    echo "  👉 Android Access URL:   http://$TAILSCALE_IP:$PORT"
else
    echo "  ℹ️  Tailscale CLI not detected or inactive."
    echo "  👉 Local Access URL:       http://localhost:$PORT"
    echo "  👉 Network Access URL:     http://<host-ip>:$PORT"
fi
echo "=========================================================="
echo "Starting FastAPI server on $HOST:$PORT..."

# Run uvicorn
exec python3 -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT" --reload
