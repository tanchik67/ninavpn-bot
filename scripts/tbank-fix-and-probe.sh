#!/usr/bin/env bash
# Обновить код с GitHub, применить TBANK_* из .env, перезапустить бота, проверить Init.
# На сервере:
#   curl -fsSL https://raw.githubusercontent.com/tanchik67/ninavpn-bot/main/scripts/tbank-fix-and-probe.sh | bash

set -euo pipefail

ROOT="${ROOT:-/opt/ninavpn-bot}"
GITHUB_TAR="${GITHUB_TAR:-https://github.com/tanchik67/ninavpn-bot/archive/refs/heads/main.tar.gz}"

mkdir -p "$ROOT"
cd "$ROOT"

env_bak=$(mktemp)
[[ -f .env ]] && cp .env "$env_bak"

echo "→ обновление кода с GitHub"
staging=$(mktemp -d)
curl -fsSL "$GITHUB_TAR" | tar xzf - -C "$staging" --strip-components=1
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude '.env' --exclude 'venv/' --exclude '*.db' --exclude '.git/' \
    "$staging/" "$ROOT/"
else
  (cd "$staging" && tar cf - --exclude='.env' --exclude='venv' --exclude='*.db' .) | (cd "$ROOT" && tar xf -)
fi
rm -rf "$staging"
[[ -s "$env_bak" ]] && cp "$env_bak" .env && chmod 600 .env
rm -f "$env_bak"
echo "✓ код обновлён"

echo "→ TBANK .env"
bash "$ROOT/scripts/tbank-env-apply.sh"

echo "→ перезапуск бота"
sudo systemctl restart ninavpn-bot
sleep 2

echo "→ probe Init"
bash "$ROOT/scripts/tbank-init-probe.sh"
