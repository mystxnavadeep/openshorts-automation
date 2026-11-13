#!/bin/sh
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/.." && pwd)"
PID_FILE="$REPO_ROOT/.server.pid"
LOG_FILE="$REPO_ROOT/logs/dashboard.log"

echo "=========================================================="
echo "        OpenShorts Dashboard Host Status Check            "
echo "=========================================================="

PORT="8000"
if [ -f "$REPO_ROOT/.env" ]; then
    ENV_PORT=$(grep -E "^PORT=" "$REPO_ROOT/.env" | cut -d'=' -f2 | tr -d '"' | tr -d "'" | tr -d ' ' || true)
    if [ -n "$ENV_PORT" ]; then
        PORT="$ENV_PORT"
    fi
fi

RUNNING=false
PID=""

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        RUNNING=true
    fi
fi

if ! $RUNNING; then
    # Try pgrep
    PID=$(pgrep -f "backend.app.main:app" 2>/dev/null | head -n 1 || true)
    if [ -n "$PID" ]; then
        RUNNING=true
    fi
fi

# Detect Tailscale IP
TAILSCALE_IP=""
if command -v tailscale >/dev/null 2>&1; then
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || true)
fi
if [ -z "$TAILSCALE_IP" ]; then
    TAILSCALE_IP=$(ip -4 addr 2>/dev/null | grep -oE "100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}" | head -n 1 || true)
fi
if [ -z "$TAILSCALE_IP" ]; then
    TAILSCALE_IP=$(ifconfig 2>/dev/null | grep -oE "100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}" | head -n 1 || true)
fi

if $RUNNING; then
    echo "🟢 Service State: RUNNING (PID: $PID)"
    echo "📡 Local URL:     http://127.0.0.1:$PORT"
    if [ -n "$TAILSCALE_IP" ]; then
        echo "🔒 Tailscale IP:  $TAILSCALE_IP"
        echo "👉 Phone URL:     http://$TAILSCALE_IP:$PORT"
    else
        echo "🔒 Tailscale IP:  Not detected on active network interfaces"
        echo "   👉 Connect the Tailscale Android App on this tablet to obtain a 100.x.y.z IP."
    fi

    # Query health endpoint
    echo ""
    echo "🧪 Testing Backend Health (/health)..."
    HEALTH=$(curl -s -m 3 "http://127.0.0.1:$PORT/health" 2>/dev/null || true)
    if [ -n "$HEALTH" ]; then
        echo "✓ Response: $HEALTH"
    else
        echo "⚠️ Health endpoint did not respond within 3 seconds."
    fi
else
    echo "🔴 Service State: STOPPED"
    echo "Run './scripts/start.sh' to start the dashboard."
fi

if [ -f "$LOG_FILE" ]; then
    echo ""
    echo "📋 Recent Server Logs (last 8 lines):"
    echo "----------------------------------------------------------"
    tail -n 8 "$LOG_FILE"
    echo "----------------------------------------------------------"
fi

echo "=========================================================="
