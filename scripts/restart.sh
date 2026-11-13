#!/bin/sh
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔄 Restarting OpenShorts Dashboard..."
"$DIR/stop.sh"
sleep 1
"$DIR/start.sh" "$@"
