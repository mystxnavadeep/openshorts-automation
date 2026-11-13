#!/bin/sh
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi
set -e

# ==============================================================================
# Helper Script: Safely Export rclone Google Drive Config to GitHub Secrets
# Never prints tokens or secrets to stdout/terminal!
# ==============================================================================

RCLONE_CONF="${HOME}/.config/rclone/rclone.conf"
REPO="mystxnavadeep/openshorts-automation"

echo "=========================================================="
echo "    rclone to GitHub Secret Safe Exporter Utility         "
echo "=========================================================="

if [ ! -f "$RCLONE_CONF" ]; then
    echo "❌ Error: rclone configuration file not found at: $RCLONE_CONF"
    echo "Please configure your Google Drive remote first with: rclone config"
    exit 1
fi

echo "🔍 Checking rclone remotes..."
if ! rclone listremotes | grep -q "gdrive:"; then
    echo "⚠️ Warning: 'gdrive:' remote not found in your remotes!"
    echo "Your available remotes are:"
    rclone listremotes
    echo "Make sure your Google Drive remote is named 'gdrive' or update the workflow input."
fi

echo "✓ Found rclone.conf at: $RCLONE_CONF"

# Check if gh CLI is available and authenticated
if command -v gh >/dev/null 2>&1; then
    echo "✓ GitHub CLI (gh) detected."
    echo "Setting 'RCLONE_CONFIG_DATA' GitHub Secret for repository: $REPO ..."
    
    # Base64 encode and set secret directly without printing to terminal
    B64_DATA=$(base64 -w 0 "$RCLONE_CONF" 2>/dev/null || base64 "$RCLONE_CONF" | tr -d '\n')
    gh secret set RCLONE_CONFIG_DATA --body "$B64_DATA" --repo "$REPO"
    
    echo "✅ SUCCESS! Secret 'RCLONE_CONFIG_DATA' has been set in repository $REPO!"
    echo "GitHub Actions can now authenticate with Google Drive securely."
else
    echo "ℹ️ GitHub CLI (gh) not detected."
    echo "To set manually, encode your rclone.conf to base64:"
    echo "  base64 -w 0 ~/.config/rclone/rclone.conf > rclone_b64.txt"
    echo "Copy the content of rclone_b64.txt into GitHub Repo Settings -> Secrets -> RCLONE_CONFIG_DATA"
    echo "Then delete rclone_b64.txt: rm -f rclone_b64.txt"
fi

echo "=========================================================="
