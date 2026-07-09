#!/usr/bin/env bash
# Одноразовая настройка сервера: deploy-ключ GitHub Actions + код с GitHub + Т-Банк.
# Запуск НА СЕРВЕРЕ (консоль it-garage / SSH):
#
#   curl -fsSL https://raw.githubusercontent.com/tanchik67/ninavpn-bot/main/scripts/server-remote-bootstrap.sh | bash
#
set -euo pipefail

DEPLOY_PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFJCxKEZ65XMbKdqz7Nr7Bcx99QKjrRXVjUneF9xXr8j ninavpn-github-actions-deploy"
ROOT="${ROOT:-/opt/ninavpn-bot}"
GITHUB_REPO="${GITHUB_REPO:-tanchik67/ninavpn-bot}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"
GITHUB_TAR="https://github.com/${GITHUB_REPO}/archive/refs/heads/${GITHUB_BRANCH}.tar.gz"

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

mkdir -p "$ROOT"
cd "$ROOT"

sync_from_github() {
  local staging
  staging=$(mktemp -d)
  trap 'rm -rf "$staging"' RETURN

  echo "→ загрузка кода: $GITHUB_TAR"
  curl -fsSL "$GITHUB_TAR" | tar xzf - -C "$staging" --strip-components=1

  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude '.env' \
      --exclude 'venv/' \
      --exclude '__pycache__/' \
      --exclude '*.db' \
      --exclude '.git/' \
      "$staging/" "$ROOT/"
  else
    echo "→ rsync не найден, копируем через tar (без .env / venv / *.db)"
    (cd "$staging" && tar cf - \
      --exclude='.env' \
      --exclude='venv' \
      --exclude='__pycache__' \
      --exclude='*.db' \
      . ) | (cd "$ROOT" && tar xf -)
  fi
  echo "✓ код обновлён из GitHub ( .env и venv не тронуты )"
}

if [[ -d .git ]]; then
  echo "→ git fetch origin $GITHUB_BRANCH"
  git fetch origin "$GITHUB_BRANCH"
  git reset --hard "origin/${GITHUB_BRANCH}"
else
  echo "! Нет .git — синхронизация архивом с GitHub"
  sync_from_github
  if command -v git >/dev/null 2>&1; then
    if [[ ! -d .git ]]; then
      git init -q
      git remote add origin "https://github.com/${GITHUB_REPO}.git" 2>/dev/null || \
        git remote set-url origin "https://github.com/${GITHUB_REPO}.git"
    fi
    git fetch -q origin "$GITHUB_BRANCH" || true
    git checkout -B "$GITHUB_BRANCH" "origin/${GITHUB_BRANCH}" 2>/dev/null || \
      git branch -M "$GITHUB_BRANCH" 2>/dev/null || true
    echo "✓ git инициализирован для будущих git pull"
  fi
fi

if [[ ! -f scripts/tbank-on-server-setup.sh ]]; then
  echo "Ошибка: после синхронизации нет scripts/tbank-on-server-setup.sh"
  exit 1
fi

bash scripts/tbank-on-server-setup.sh
