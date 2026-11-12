# Google Drive (rclone) Integration Guide

This guide explains how to connect your existing `rclone` Google Drive remote (`gdrive:`) to the GitHub Actions processing pipeline so that generated shorts are permanently saved to your Google Drive.

---

## 🏗️ How It Works

```
┌─────────────────────────────────────────────────────────────┐
│ GitHub Actions Runner (Ubuntu)                             │
│                                                             │
│  1. Video Processing finishes -> output/short_01.mp4        │
│  2. Reads secret RCLONE_CONFIG_DATA                         │
│  3. Decodes into ~/.config/rclone/rclone.conf               │
│  4. Runs: rclone copy output/ gdrive:OpenShorts/Run-42      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
            ┌────────────────────────────────────┐
            │ Google Drive (Remote: 'gdrive')    │
            │ 📁 OpenShorts                      │
            │   └── 📁 Run-42                    │
            │       ├── short_01.mp4             │
            │       ├── short_02.mp4             │
            │       └── metadata.json            │
            └────────────────────────────────────┘
```

---

## 🔑 Exporting Your Local rclone Config to GitHub Secrets

Since you already have a working `rclone` Google Drive remote named `gdrive:`, you only need to export your `rclone.conf` into a GitHub Secret named **`RCLONE_CONFIG_DATA`**.

### Method 1: Automated Safe Script (Recommended)

Run our included safe exporter script:
```bash
./scripts/export_rclone_secret.sh
```
This script automatically base64-encodes your configuration and sets the secret directly via the GitHub CLI without echoing tokens to your screen.

---

### Method 2: Manual Export via Terminal

1. Locate your rclone config file (typically `~/.config/rclone/rclone.conf`).
2. Generate the Base64-encoded string:
   ```bash
   base64 -w 0 ~/.config/rclone/rclone.conf
   ```
   *(On macOS / BSD: `base64 < ~/.config/rclone/rclone.conf | tr -d '\n'`)*
3. Copy the base64 output.
4. Go to your GitHub repository:
   **https://github.com/mystxnavadeep/openshorts-automation/settings/secrets/actions**
5. Click **New repository secret**:
   - **Name**: `RCLONE_CONFIG_DATA`
   - **Secret**: *(Paste the base64 string)*
6. Click **Add secret**.

---

## 📁 Destination Folder Structure

In the dashboard or workflow input, you can specify `gdrive_folder` (default: `OpenShorts`).

Each execution uploads its outputs into a subfolder named after the GitHub Actions run number:
```text
gdrive:
  └── OpenShorts/
      └── Run-<RunNumber>/
          ├── short_01.mp4
          ├── short_02.mp4
          ├── short_03.mp4
          └── metadata.json
```

---

## 🔒 Token Expiration & Refreshing

Google OAuth tokens in `rclone.conf` include a `refresh_token`. The GitHub Actions runner uses this refresh token to generate temporary access tokens on the fly, meaning your secret does not expire on a daily or weekly basis. If your Google account password changes or access is revoked, simply re-run `rclone config reconnect gdrive:` and re-export the secret.
