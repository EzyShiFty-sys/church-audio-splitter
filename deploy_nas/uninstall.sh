#!/usr/bin/env bash
# Uninstall script for House of Refuge Audio Splitter on UGREEN NAS

set -e

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo bash uninstall.sh"
  exit 1
fi

echo "Stopping and removing church-splitter systemd service..."
systemctl stop church-splitter.service || true
systemctl disable church-splitter.service || true
rm -f /etc/systemd/system/church-splitter.service
systemctl daemon-reload

echo "Removing application files from /opt/church-audio-splitter..."
rm -rf /opt/church-audio-splitter

echo "✓ Uninstalled successfully."
