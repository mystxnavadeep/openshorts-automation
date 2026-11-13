"""
Security, URL validation, and duplicate submission protection.
"""

import os
import re
import subprocess
import time
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

# Strict regex patterns for valid YouTube video URLs
YOUTUBE_PATTERNS = [
    re.compile(r"^(https?://)?(www\.|m\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})"),
    re.compile(r"^(https?://)?youtu\.be/([a-zA-Z0-9_-]{11})"),
    re.compile(r"^(https?://)?(www\.|m\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})"),
    re.compile(r"^(https?://)?(www\.|m\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})"),
    re.compile(r"^(https?://)?(www\.|m\.)?youtube\.com/live/([a-zA-Z0-9_-]{11})"),
]

# Prohibited paths (playlists, channels, feeds, search)
DISALLOWED_PATHS = {
    "results", "playlist", "hashtag", "channel", "c", "user", "feed",
    "gaming", "music", "podcasts"
}

# Duplicate tracking cache: {video_id: timestamp}
_RECENT_DISPATCHES = {}
DEDUP_WINDOW_SECONDS = 90


def extract_youtube_video_id(url: str) -> Optional[str]:
    """
    Validates and extracts an 11-character YouTube video ID.
    Returns None if the URL is invalid, malicious, or not a single video.
    """
    if not url or not isinstance(url, str):
        return None

    cleaned_url = url.strip()

    # Parse URL to check domain and path
    try:
        parsed = urlparse(cleaned_url)
    except Exception:
        return None

    domain = parsed.netloc.lower()
    path = parsed.path.strip("/").split("/")

    # Check for known YouTube hostnames
    if not any(domain.endswith(h) for h in ["youtube.com", "youtu.be"]):
        return None

    # Check for disallowed YouTube paths
    if path and path[0].lower() in DISALLOWED_PATHS:
        return None

    # Match against patterns
    for pattern in YOUTUBE_PATTERNS:
        match = pattern.search(cleaned_url)
        if match:
            # The last captured group is the 11-char video ID
            return match.group(match.lastindex)

    # Fallback: check query params if watch
    if "watch" in parsed.path:
        params = parse_qs(parsed.query)
        v = params.get("v")
        if v and len(v[0]) == 11 and re.match(r"^[a-zA-Z0-9_-]{11}$", v[0]):
            return v[0]

    return None


def canonical_youtube_url(video_id: str) -> str:
    """Returns canonical YouTube URL from a validated video ID."""
    return f"https://www.youtube.com/watch?v={video_id}"


def check_and_record_dispatch(video_id: str) -> Tuple[bool, Optional[int]]:
    """
    Checks if a video was recently dispatched.
    Returns (allowed, seconds_remaining).
    """
    now = time.time()
    # Prune old records
    expired = [k for k, ts in _RECENT_DISPATCHES.items() if now - ts > DEDUP_WINDOW_SECONDS]
    for k in expired:
        _RECENT_DISPATCHES.pop(k, None)

    if video_id in _RECENT_DISPATCHES:
        elapsed = now - _RECENT_DISPATCHES[video_id]
        if elapsed < DEDUP_WINDOW_SECONDS:
            remaining = int(DEDUP_WINDOW_SECONDS - elapsed)
            return False, remaining

    _RECENT_DISPATCHES[video_id] = now
    return True, None


def get_tailscale_ip() -> Optional[str]:
    """
    Detects Tailscale IPv4 address on both standard Linux hosts and Android/Termux environments.
    Checks:
    1. TAILSCALE_IP environment variable override (if configured in .env)
    2. tailscale CLI command (if installed)
    3. ip -4 addr interface inspection (for Android tun0 VPN interface)
    4. ifconfig interface output
    """
    # 1. Environment variable override
    env_ip = os.getenv("TAILSCALE_IP", "").strip()
    if env_ip.startswith("100."):
        return env_ip

    # 2. Try tailscale CLI
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            ip = result.stdout.strip().split("\n")[0].strip()
            if ip.startswith("100."):
                return ip
    except Exception:
        pass

    # 3. Check ip -4 addr
    try:
        r = subprocess.run(["ip", "-4", "addr"], capture_output=True, text=True, timeout=1)
        if r.returncode == 0:
            matches = re.findall(r"inet\s+(100\.\d{1,3}\.\d{1,3}\.\d{1,3})", r.stdout)
            if matches:
                return matches[0]
    except Exception:
        pass

    # 4. Check ifconfig
    try:
        r = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=1)
        if r.returncode == 0:
            matches = re.findall(r"inet\s+(?:addr:)?(100\.\d{1,3}\.\d{1,3}\.\d{1,3})", r.stdout)
            if matches:
                return matches[0]
    except Exception:
        pass

    return None
