# Security & Hardening Model

This project is designed from the ground up with **Defense in Depth** to guarantee privacy, prevent credential leakage, and protect against network attacks.

---

## 🔒 1. Zero Public Port Exposure (Tailscale Mesh)

- **No Port Forwarding**: Port `8000` is never forwarded through consumer NAT routers or public firewalls.
- **Peer-to-Peer Encryption**: All HTTP traffic between your Android device and the dashboard host is encapsulated within encrypted **WireGuard®** tunnels.
- **Strict Host Binding**:
  - The dashboard server can be bound strictly to the `tailscale0` network interface or your host's private Tailscale IP (`100.x.y.z`).
  - Public interface scanners (Shodan, Censys) will find zero open ports.

---

## 🔑 2. Credential Isolation & Token Hygiene

- **Frontend Isolation**:
  - Frontend JavaScript **NEVER** handles or stores your `GITHUB_TOKEN` or `GEMINI_API_KEY`.
  - All GitHub API dispatches are brokered exclusively by the Python FastAPI backend.
  - Client configuration endpoints (`/api/config`) explicitly strip credentials before returning data to the browser.
- **GitHub Secrets Protection**:
  - `GEMINI_API_KEY` and `RCLONE_CONFIG_DATA` reside strictly in GitHub Encrypted Repository Secrets.
  - GitHub Actions automatically masks these secrets in runner console logs.
- **Least Privilege Tokens**:
  - The personal access token (`GITHUB_TOKEN`) requires only the `workflow` scope (or `repo` scope for private repositories) to trigger `workflow_dispatch`. Do NOT grant admin or billing scopes.

---

## 🛡️ 3. Input Validation & SSRF Guard

- **Strict URL Whitelisting**:
  - Submissions are validated against strict regex patterns matching only valid YouTube video IDs (`watch?v=`, `youtu.be/`, `/shorts/`).
  - Arbitrary HTTP/HTTPS URLs, localhost addresses (`127.0.0.1`), metadata endpoints (`169.254.169.254`), and non-video YouTube pages (search, channels, playlists) are rejected with HTTP 400.
- **Duplicate Dispatch Protection**:
  - An in-memory deduplication cache prevents rapid-fire duplicate submissions of the same video within a 90-second cooldown window.

---

## ☁️ 4. Google Drive Security

- Your `rclone.conf` is stored as an encrypted base64 GitHub Secret.
- The workflow decodes the configuration into an ephemeral file with `chmod 600` permissions.
- Google OAuth refresh tokens grant access only to Google Drive files; they cannot access Gmail or Google account settings.
