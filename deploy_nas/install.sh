#!/usr/bin/env bash
# ==============================================================================
# House of Refuge Church - Audio Splitter NAS Deployment Script
# Targets: UGREEN NAS (Debian Linux ARM64 / aarch64 - Rockchip RK3576)
# Sets up 24/7 background systemd service on port 8000
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
  echo "❌ Error: Please run this script as root: sudo bash install.sh"
  exit 1
fi

echo "======================================================================"
echo "    House of Refuge Church - Audio Splitter 24/7 NAS Installer"
echo "                https://houseofrefugechurch.net/"
echo "======================================================================"
echo ""

INSTALL_DIR="/opt/church-audio-splitter"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 1. Update package lists and install system packages
echo "[1/6] Installing system prerequisites (Python 3, FFmpeg, Git)..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv ffmpeg git curl libsndfile1

# 2. Prepare installation directory
echo "[2/6] Setting up application directory at ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
cp -r "${REPO_DIR}/src" "${INSTALL_DIR}/"
cp -r "${REPO_DIR}/static" "${INSTALL_DIR}/"
cp "${REPO_DIR}/pyproject.toml" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/church-splitter.service" "${INSTALL_DIR}/"

# 3. Create Python Virtual Environment
echo "[3/6] Creating Python virtual environment (ARM64 optimized)..."
python3 -m venv "${INSTALL_DIR}/venv"
source "${INSTALL_DIR}/venv/bin/activate"

# 4. Install Python dependencies
echo "[4/6] Installing application libraries (FastAPI, Whisper, etc.)..."
pip install --upgrade pip
pip install fastapi uvicorn faster-whisper soundfile numpy mutagen pydantic python-multipart rich tqdm

# 5. Pre-download lightweight Whisper models (tiny & base)
echo "[5/6] Pre-caching Whisper speech models (runs offline & in-memory)..."
python3 -c "
from faster_whisper import WhisperModel
print('Downloading base model...')
WhisperModel('base', device='cpu', compute_type='int8')
print('Downloading tiny model...')
WhisperModel('tiny', device='cpu', compute_type='int8')
print('✓ Speech models pre-cached successfully!')
"

# 6. Install and enable systemd 24/7 background service
echo "[6/6] Installing and starting systemd 24/7 background service..."
cp "${INSTALL_DIR}/church-splitter.service" /etc/systemd/system/church-splitter.service
systemctl daemon-reload
systemctl enable church-splitter.service
systemctl restart church-splitter.service

# Get primary IP
NAS_IP=$(hostname -I | awk '{print $1}' || echo "192.168.0.199")

echo ""
echo "======================================================================"
echo "  🎉 SUCCESS! The House of Refuge Audio Splitter is now running 24/7!"
echo "======================================================================"
echo ""
echo "  🌐 Access the Web Dashboard from any computer, tablet, or phone at:"
echo "     👉 http://${NAS_IP}:8000"
echo ""
echo "  ⚙️ Useful Management Commands:"
echo "     - Check status:  sudo systemctl status church-splitter"
echo "     - View live logs: sudo journalctl -u church-splitter -f"
echo "     - Restart app:   sudo systemctl restart church-splitter"
echo "     - Stop app:      sudo systemctl stop church-splitter"
echo "======================================================================"
