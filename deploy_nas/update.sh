#!/usr/bin/env bash
# Update script for House of Refuge Audio Splitter on UGREEN NAS

set -e

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo bash update.sh"
  exit 1
fi

INSTALL_DIR="/opt/church-audio-splitter"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Updating application files at ${INSTALL_DIR}..."
cp -r "${REPO_DIR}/src" "${INSTALL_DIR}/"
cp -r "${REPO_DIR}/static" "${INSTALL_DIR}/"
cp "${REPO_DIR}/pyproject.toml" "${INSTALL_DIR}/"

echo "Restarting church-splitter service..."
systemctl restart church-splitter.service

echo "✓ Application updated and restarted successfully!"
