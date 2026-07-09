#!/usr/bin/env bash
# Одноразовая настройка сервера: deploy-ключ GitHub Actions + git pull + Т-Банк.
# Запуск НА СЕРВЕРЕ (консоль it-garage / SSH):
#
#   curl -fsSL https://raw.githubusercontent.com/tanchik67/ninavpn-bot/main/scripts/server-remote-bootstrap.sh | bash
#
set -euo pipefail

DEPLOY_PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFJCxKEZ65XMbKdqz7Nr7Bcx99QKjrRXVjUneF9xXr8j ninavpn-github-actions-deploy"
ROOT="${ROOT:-/opt/ninavpn-bot}"

echo "=== NINAVPN: remote bootstrap ==="

mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
if ! grep -qF "$DEPLOY_PUBKEY" ~/.ssh/authorized_keys 2>/dev/null; then
  echo "$DEPLOY_PUBKEY" >> ~/.ssh/authorized_keys
  echo "✓ deploy-ключ GitHub Actions добавлен в authorized_keys"
else
  echo "✓ deploy-ключ уже в authorized_keys"
fi

if [[ ! -d "$ROOT" ]]; then
  echo "Ошибка: нет $ROOT"
  exit 1
fi

cd "$ROOT"
if [[ -d .git ]]; then
  git fetch origin main
  git reset --hard origin/main
else
  echo "! Нет .git — пропускаем git pull (скопируйте код вручную или клонируйте репозиторий)"
fi

if [[ -f scripts/tbank-on-server-setup.sh ]]; then
  bash scripts/tbank-on-server-setup.sh
else
  echo "Ошибка: нет scripts/tbank-on-server-setup.sh — сначала обновите код в $ROOT"
  exit 1
fi
