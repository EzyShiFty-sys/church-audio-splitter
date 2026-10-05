# ⛪ Running Church Audio Splitter 24/7 on UGREEN NAS (DH2300)

Your UGREEN NAS DH2300 runs **UGOS Pro**, which is built on Debian Linux. By enabling SSH, you can run the Audio Splitter directly as a background **systemd service** that starts automatically on boot and stays running **24/7**.

Once deployed, anyone on the church network can access the dashboard at:
👉 **`http://192.168.0.199:8000`** (or your NAS's IP).

---

## 🚀 Setup Steps (5 Minutes)

### Step 1: Enable SSH on Your UGREEN NAS
1. Log into your UGREEN NAS web desktop in your browser.
2. Open **Control Panel** > **Terminal**.
3. Check the box for **Enable SSH** (Port `22`).
4. Click **Apply**.

---

### Step 2: Connect to the NAS via Terminal / PowerShell
On your Windows PC (or Mac/Linux), open **PowerShell** or **Command Prompt** and run:

```bash
ssh <your_nas_username>@192.168.0.199
```
*(Replace `<your_nas_username>` with your UGREEN admin account name, e.g. `admin`)*

Type your password when prompted and press Enter.

---

### Step 3: Download the Repository on the NAS
Inside your SSH terminal session on the NAS, run:

```bash
git clone https://github.com/EzyShiFty-sys/church-audio-splitter.git
cd church-audio-splitter
```

---

### Step 4: Run the Automated 1-Click Installer
Run the installation script:

```bash
sudo bash deploy_nas/install.sh
```

**What this automated script does:**
1. Installs Python 3, FFmpeg, and audio libraries using Debian's `apt`.
2. Creates an ARM64-optimized virtual environment at `/opt/church-audio-splitter`.
3. Installs FastAPI, faster-whisper, and web dependencies.
4. Pre-caches the lightweight Whisper models (`base` and `tiny`) with `int8` quantization (~250MB RAM footprint).
5. Installs and registers the `church-splitter.service` system daemon with auto-restart.
6. Launches the web server on port `8000`.

---

### Step 5: Open in Your Browser!
You're done! Open your web browser on any computer, tablet, or phone on the church network:

👉 **`http://192.168.0.199:8000`**

The service is permanently running in the background and will automatically restart whenever the NAS is rebooted.

---

## 🛠️ Service Management Commands (on the NAS)

| Action | Command |
| :--- | :--- |
| **Check Live Status** | `sudo systemctl status church-splitter` |
| **View Live Server Logs** | `sudo journalctl -u church-splitter -f` |
| **Restart App** | `sudo systemctl restart church-splitter` |
| **Stop App** | `sudo systemctl stop church-splitter` |
| **Update to Latest Code** | `cd church-audio-splitter && git pull && sudo bash deploy_nas/update.sh` |
| **Uninstall Cleanly** | `sudo bash deploy_nas/uninstall.sh` |
