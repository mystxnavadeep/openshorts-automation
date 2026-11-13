#!/bin/sh
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi
set -e

# ==============================================================================
# OpenShorts Dashboard Host Setup Script
# Configured specifically for Samsung Galaxy Tab A9 X110 (Android/Termux ARM64)
# and standard Linux environments.
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================================="
echo "    OpenShorts Automation Host Setup (Android / Termux)   "
echo "=========================================================="

# 1. Architecture & Python Check
ARCH=$(uname -m)
OS=$(uname -o 2>/dev/null || uname -s)
echo "📱 Device / Environment:"
echo "  • Operating System: $OS"
echo "  • Architecture:     $ARCH"
echo "  • Python Version:   $(python3 --version 2>&1)"

# 2. Check and configure .env
if [ ! -f "$REPO_ROOT/.env" ]; then
    echo ""
    echo "📝 Creating .env from .env.example..."
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
    echo "✓ Created .env"
fi

# 3. Install compatible Python dependencies
echo ""
echo "📦 Installing compatible backend dependencies..."
# On Termux ARM64 (Python 3.14), pydantic<2 and fastapi<0.100 install with pure-Python wheels
# avoiding complex Rust/C compilation (maturin) issues:
python3 -m pip install -r "$REPO_ROOT/backend/requirements.txt"

# 4. Check GitHub CLI authentication
echo ""
echo "🔑 Checking GitHub API credentials..."
if command -v gh >/dev/null 2>&1; then
    if gh auth status >/dev/null 2>&1; then
        echo "✓ GitHub CLI (gh) is authenticated!"
        GH_CLI_TOKEN=$(gh auth token 2>/dev/null || true)
        if [ -n "$GH_CLI_TOKEN" ] && [ -f "$REPO_ROOT/.env" ]; then
            if grep -q "ghp_yourPersonalAccessTokenHere" "$REPO_ROOT/.env"; then
                sed -i "s/GITHUB_TOKEN=ghp_yourPersonalAccessTokenHere/GITHUB_TOKEN=$GH_CLI_TOKEN/" "$REPO_ROOT/.env"
                echo "✓ Auto-configured GITHUB_TOKEN in .env from authenticated GitHub CLI!"
            fi
        fi
    else
        echo "⚠️ GitHub CLI is installed but not authenticated. Run: gh auth login"
    fi
else
    echo "ℹ️ GitHub CLI (gh) not found. Ensure GITHUB_TOKEN is set in .env"
fi

# 5. Check Tailscale
echo ""
echo "🔒 Checking Tailscale configuration..."
if command -v tailscale >/dev/null 2>&1; then
    TS_IP=$(tailscale ip -4 2>/dev/null || true)
    if [ -n "$TS_IP" ]; then
        echo "✓ Tailscale CLI detected. IP: $TS_IP"
    fi
else
    echo "ℹ️ On Android/Termux, install the official Tailscale app from Play Store/F-Droid."
    echo "   Turn on Tailscale in the app to assign this tablet a 100.x.y.z IP."
fi

# 6. Verify backend imports
echo ""
echo "🧪 Verifying backend imports..."
python3 -c "import backend.app.main; print('✓ Backend loaded successfully!')"

echo ""
echo "=========================================================="
echo "🎉 Setup complete! You can now start the dashboard using:"
echo "   ./scripts/start.sh"
echo "=========================================================="
