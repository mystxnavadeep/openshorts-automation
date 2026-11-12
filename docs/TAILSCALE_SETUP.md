# Tailscale Dashboard Deployment & Android Access Guide

This guide walks you through setting up **Tailscale** to securely access your OpenShorts dashboard from your Android phone anywhere in the world, with **zero public ports** and **zero exposure** to the public internet.

---

## 🌟 Why Tailscale?

Traditional self-hosting requires opening router ports (Port Forwarding), dynamic DNS, and risking automated web scanners probing your personal servers.

Tailscale builds an encrypted WireGuard® mesh network (your **Tailnet**) where:
- Your dashboard host and your Android phone communicate directly peer-to-peer.
- Every node receives a stable, private 100.x.y.z IP and MagicDNS domain.
- All dashboard ports (e.g., `8000`) stay strictly private.

---

## 📱 Part 1: Setting up Tailscale on Android

1. **Install Tailscale App**:
   - Download **Tailscale** from [Google Play Store](https://play.google.com/store/apps/details?id=com.tailscale.ipn) or [F-Droid](https://f-droid.org/packages/com.tailscale.ipn/).
2. **Log In**:
   - Sign in using your Google, GitHub, or Microsoft account.
3. **Connect**:
   - Toggle the main connection switch to **Active**.
   - Android will request permission to establish a VPN connection. Tap **OK / Allow**.
4. **Verify**:
   - Open the Tailscale app; you will see your Android device's name and its private `100.x.y.z` IP address.

---

## 🖥️ Part 2: Setting up Tailscale on the Dashboard Host

You can run the always-on dashboard on any machine: a lightweight Linux VPS (Hetzner, Oracle Cloud Free Tier, DigitalOcean), a home server, Raspberry Pi, or local environment.

### 1. Install Tailscale on Linux (Debian / Ubuntu / Raspberry Pi OS):
```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

### 2. Authenticate the Host into your Tailnet:
```bash
sudo tailscale up
```
Follow the printed URL in your browser to authorize the host into the same Tailnet as your Android phone.

### 3. Retrieve the Host's Tailscale IP:
```bash
tailscale ip -4
# Example output: 100.85.24.112
```

---

## 🚀 Part 3: Running the Dashboard Server

### Option A: Direct Bash Execution (Recommended)
1. Clone your repository:
   ```bash
   git clone https://github.com/mystxnavadeep/openshorts-automation.git
   cd openshorts-automation
   ```
2. Create and configure your `.env`:
   ```bash
   cp .env.example .env
   nano .env
   # Set GITHUB_TOKEN=ghp_yourPersonalAccessToken
   ```
3. Install backend dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
4. Start the server:
   ```bash
   ./backend/run.sh
   ```
   The launcher script automatically detects your Tailscale IP and prints the URL!

### Option B: Docker Compose
```bash
cd openshorts-automation/deploy
docker compose up -d
```

### Option C: Systemd Service (Always-On 24/7)
```bash
sudo cp deploy/systemd/openshorts-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now openshorts-dashboard
```

---

## 📲 Part 4: Accessing the Dashboard from Android

1. Ensure **Tailscale is toggled ON** on your Android device.
2. Open any web browser on your Android phone (Chrome, Firefox, Brave).
3. Navigate to:
   ```text
   http://100.x.y.z:8000
   ```
   *(Replace `100.x.y.z` with your dashboard host's Tailscale IP, or use MagicDNS e.g. `http://openshorts-server:8000`)*
4. You will see the sleek, dark-mode OpenShorts automation interface!
5. Bookmark the page or tap **"Add to Home screen"** in Chrome for a native app feel!

---

## 🔒 Optional: HTTPS with Tailscale Serve (Port 443)

Tailscale provides built-in HTTPS certificates for your MagicDNS domain:
```bash
# Automatically proxies port 8000 to port 443 with a valid Let's Encrypt SSL certificate:
tailscale serve https / http://127.0.0.1:8000
```
After running this, you can visit `https://<node-name>.<tailnet-name>.ts.net` with zero browser SSL warnings!

---

## 🛠️ Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Android browser says "Site can't be reached"** | Tailscale VPN is paused on Android | Open Tailscale app and verify status is "Connected" |
| **Connection timed out** | Host firewall blocking port 8000 on tailscale0 interface | Allow port 8000 for Tailscale: `sudo ufw allow in on tailscale0 to any port 8000` |
| **MagicDNS name doesn't resolve** | MagicDNS disabled in Tailscale Admin Console | Use direct `100.x.y.z` IP address or enable MagicDNS in admin console |
