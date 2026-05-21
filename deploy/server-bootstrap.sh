#!/usr/bin/env bash
#
# One-time bootstrap for a fresh Ubuntu/Debian server.
# Run this ON the server (2.27.123.28) as root or via sudo.
#
# What it installs:
# - Python build/run deps for the bot
# - nginx + certbot (optional; you still need DNS ready for cert issuance)
#
set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Please run as root (or: sudo bash $0)"
  exit 1
fi

apt update
apt install -y \
  python3 python3-venv python3-pip \
  nginx certbot python3-certbot-nginx \
  ca-certificates curl git

echo ""
echo "Installed base packages."
echo "Next steps:"
echo "1) Point DNS ninavpn.store -> 2.27.123.28"
echo "2) Issue cert: certbot --nginx -d ninavpn.store"
echo "3) Deploy code to /opt/ninavpn-bot"
echo "4) Create /opt/ninavpn-bot/.env from .env.example"
echo "5) systemd: cp ninavpn-bot.service to /etc/systemd/system and start"

