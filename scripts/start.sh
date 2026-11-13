#!/bin/sh
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/.." && pwd)"
cd "$REPO_ROOT"

PID_FILE="$REPO_ROOT/.server.pid"
LOG_DIR="$REPO_ROOT/logs"
LOG_FILE="$LOG_DIR/dashboard.log"

mkdir -p "$LOG_DIR"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "⚠️ OpenShorts Dashboard is ALREADY running (PID: $PID)."
        echo "Use './scripts/status.sh' to inspect or './scripts/stop.sh' to stop."
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# Load .env if present
if [ -f "$REPO_ROOT/.env" ]; then
    # Export non-comment lines
    set -a
    source "$REPO_ROOT/.env" 2>/dev/null || true
    set +a
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

# Android Termux wake lock to prevent CPU sleep
if command -v termux-wake-lock >/dev/null 2>&1; then
    echo "⚡ Acquiring Termux CPU wake lock (prevents sleep while active)..."
    termux-wake-lock
fi

# Detect Tailscale IP if available
TAILSCALE_IP=""
if [ -n "$TAILSCALE_IP_OVERRIDE" ]; then
    TAILSCALE_IP="$TAILSCALE_IP_OVERRIDE"
elif command -v tailscale >/dev/null 2>&1; then
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || true)
fi

if [ -z "$TAILSCALE_IP" ]; then
    # Try finding 100.x.y.z from ip -4 addr
    TAILSCALE_IP=$(ip -4 addr 2>/dev/null | grep -oE "100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}" | head -n 1 || true)
fi

if [ -z "$TAILSCALE_IP" ]; then
    # Try ifconfig
    TAILSCALE_IP=$(ifconfig 2>/dev/null | grep -oE "100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}" | head -n 1 || true)
fi

echo "=========================================================="
echo "        Starting OpenShorts Automation Dashboard          "
echo "=========================================================="
echo "Host Interface: $HOST:$PORT"
if [ -n "$TAILSCALE_IP" ]; then
    echo "Tailscale IP:   $TAILSCALE_IP"
    echo "👉 Remote Phone Access URL: http://$TAILSCALE_IP:$PORT"
else
    echo "Tailscale IP:   Not active on host interface yet"
    echo "👉 Once Tailscale Android app connects, open: http://<tab-tailscale-ip>:$PORT"
fi
echo "Localhost URL:  http://127.0.0.1:$PORT"
echo "Log File:       $LOG_FILE"
echo "=========================================================="

# Check if foreground mode requested
if [ "$1" = "--foreground" ] || [ "$1" = "-f" ]; then
    echo "Running in foreground mode (Press Ctrl+C to stop)..."
    exec python3 -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT"
fi

# Run in background with setsid / nohup and detached stdio
if command -v setsid >/dev/null 2>&1; then
    setsid nohup python3 -u -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT" </dev/null >> "$LOG_FILE" 2>&1 &
else
    nohup python3 -u -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT" </dev/null >> "$LOG_FILE" 2>&1 &
fi
PID=$!
disown "$PID" 2>/dev/null || true
echo "$PID" > "$PID_FILE"

# Wait a second to verify startup
sleep 1.5

if kill -0 "$PID" 2>/dev/null; then
    echo "✅ Dashboard started successfully in background! (PID: $PID)"
    echo "Run './scripts/status.sh' to check health and status."
else
    echo "❌ Server failed to start. Showing last log output:"
    tail -n 20 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
