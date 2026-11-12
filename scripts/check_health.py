#!/usr/bin/env python3
"""
OpenShorts Health & Environment Diagnostics Utility
Verifies Tailscale IP, GitHub API token, rclone config, and pipeline dependencies.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def check_mark(success: bool) -> str:
    return "✅ [PASS]" if success else "❌ [FAIL]"


def info_mark() -> str:
    return "ℹ️ [INFO]"


def main():
    print("=" * 65)
    print("       OpenShorts Automation System Health Diagnostics        ")
    print("=" * 65)

    all_passed = True

    # 1. Python & CLI Tools
    print("\n--- 1. Core Executables & System Tools ---")
    tools = ["git", "ffmpeg", "python3", "rclone", "tailscale", "gh"]
    for tool in tools:
        found = shutil.which(tool) is not None
        status = check_mark(found)
        path_str = shutil.which(tool) or "Not found in PATH"
        print(f"{status} {tool:<12} : {path_str}")
        if tool in ["git", "python3"] and not found:
            all_passed = False
        elif tool == "ffmpeg" and not found:
            print("   💡 Note: ffmpeg is only required if processing locally. GitHub Actions runner has ffmpeg pre-installed.")

    # 2. Tailscale Network
    print("\n--- 2. Tailscale Mesh Network ---")
    tailscale_ip = None
    try:
        res = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            tailscale_ip = res.stdout.strip().split("\n")[0].strip()
    except Exception:
        pass

    if tailscale_ip and tailscale_ip.startswith("100."):
        print(f"{check_mark(True)} Tailscale IP: {tailscale_ip}")
        print(f"   👉 Android Access URL: http://{tailscale_ip}:8000")
    else:
        print(f"⚠️ [WARN] Tailscale IPv4 not detected. If running in a container or Termux, ensure Tailscale is connected.")

    # 3. GitHub API Connectivity
    print("\n--- 3. GitHub API & Workflow Authentication ---")
    token = os.getenv("GITHUB_TOKEN")
    owner = os.getenv("GITHUB_OWNER", "mystxnavadeep")
    repo = os.getenv("GITHUB_REPO", "openshorts-automation")

    if not token:
        # Check if gh CLI has auth
        try:
            gh_res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
            if gh_res.returncode == 0:
                print(f"{check_mark(True)} GitHub CLI (`gh`) is authenticated for @{owner}")
                print(f"   💡 You can extract token or run: gh secret set GEMINI_API_KEY")
            else:
                print(f"{check_mark(False)} GITHUB_TOKEN not found in .env and gh CLI not authenticated")
                all_passed = False
        except Exception:
            print(f"{check_mark(False)} GITHUB_TOKEN not configured in environment")
            all_passed = False
    else:
        print(f"{check_mark(True)} GITHUB_TOKEN configured (length: {len(token)} chars)")

    # 4. rclone Google Drive Configuration
    print("\n--- 4. Google Drive (rclone) Status ---")
    rclone_conf = Path.home() / ".config" / "rclone" / "rclone.conf"
    if rclone_conf.exists():
        print(f"{check_mark(True)} rclone configuration found at: {rclone_conf}")
        try:
            remotes_res = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True)
            if "gdrive:" in remotes_res.stdout:
                print(f"{check_mark(True)} Remote 'gdrive:' is configured and detected!")
            else:
                print(f"⚠️ [WARN] 'gdrive:' remote not found in remotes list:\n{remotes_res.stdout}")
        except Exception as e:
            print(f"⚠️ Error querying remotes: {e}")
    else:
        print(f"⚠️ [WARN] Local rclone.conf not found at {rclone_conf}")

    # 5. Gemini API Key
    print("\n--- 5. Google Gemini AI Key ---")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        print(f"{check_mark(True)} GEMINI_API_KEY configured in environment (starts with: {gemini_key[:6]}...)")
    else:
        print(f"ℹ️ [NOTE] GEMINI_API_KEY is not set in local environment. Remember to add it to GitHub Secrets!")

    print("\n" + "=" * 65)
    if all_passed:
        print("🎉 System diagnostics completed successfully!")
    else:
        print("⚠️ System diagnostics identified items requiring attention.")
    print("=" * 65)


if __name__ == "__main__":
    main()
