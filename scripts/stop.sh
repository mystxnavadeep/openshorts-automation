#!/bin/sh
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/.." && pwd)"
PID_FILE="$REPO_ROOT/.server.pid"

echo "=========================================================="
echo "        Stopping OpenShorts Automation Dashboard          "
echo "=========================================================="

if [ ! -f "$PID_FILE" ]; then
    # Also check if any uvicorn backend.app.main:app is running
    PID=$(pgrep -f "backend.app.main:app" 2>/dev/null || true)
    if [ -z "$PID" ]; then
        echo "ℹ️ Dashboard server is not running."
        exit 0
    fi
else
    PID=$(cat "$PID_FILE" 2>/dev/null || true)
fi

if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    echo "Stopping server process (PID: $PID)..."
    kill "$PID" 2>/dev/null || true
    
    # Wait up to 5 seconds
    for i in {1..5}; do
        if kill -0 "$PID" 2>/dev/null; then
            sleep 1
        else
            break
        fi
    done

    # Force kill if still alive
    if kill -0 "$PID" 2>/dev/null; then
        echo "Process did not terminate gracefully, force-killing..."
        kill -9 "$PID" 2>/dev/null || true
    fi

    echo "✅ Dashboard server stopped."
else
    echo "ℹ️ No running server found matching PID."
fi

rm -f "$PID_FILE"

# Release Termux wake lock if present
if command -v termux-wake-unlock >/dev/null 2>&1; then
    echo "⚡ Releasing Termux CPU wake lock..."
    termux-wake-unlock 2>/dev/null || true
fi

echo "=========================================================="
