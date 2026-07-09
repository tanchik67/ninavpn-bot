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
GITHUB_ORIGIN="https://github.com/${GITHUB_REPO}.git"

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

preserve_env() {
  local dest="$1"
  [[ -f .env ]] && cp .env "$dest"
}

restore_env() {
  local src="$1"
  if [[ -s "$src" ]]; then
    cp "$src" .env
    chmod 600 .env 2>/dev/null || true
  fi
}

sync_from_github_tar() {
  local staging env_bak
  staging=$(mktemp -d)
  env_bak=$(mktemp)
  preserve_env "$env_bak"
  trap 'rm -rf "$staging" "$env_bak"' RETURN

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
  restore_env "$env_bak"
  echo "✓ код обновлён из GitHub ( .env и venv не тронуты )"
}

init_git_clean() {
  local env_bak
  env_bak=$(mktemp)
  preserve_env "$env_bak"
  rm -rf .git
  git init -q
  git remote add origin "$GITHUB_ORIGIN" 2>/dev/null || git remote set-url origin "$GITHUB_ORIGIN"
  git fetch -q origin "$GITHUB_BRANCH"
  git checkout -qf -B "$GITHUB_BRANCH" "origin/${GITHUB_BRANCH}"
  restore_env "$env_bak"
  rm -f "$env_bak"
  echo "✓ git настроен (origin/${GITHUB_BRANCH})"
}

if [[ -d .git ]] && command -v git >/dev/null 2>&1; then
  echo "→ git fetch + reset --hard origin/${GITHUB_BRANCH}"
  env_bak=$(mktemp)
  preserve_env "$env_bak"
  if git fetch origin "$GITHUB_BRANCH" && git reset --hard "origin/${GITHUB_BRANCH}"; then
    restore_env "$env_bak"
    echo "✓ код синхронизирован через git"
  else
    restore_env "$env_bak"
    echo "! git reset не удался — синхронизация архивом"
    sync_from_github_tar
    init_git_clean
  fi
  rm -f "$env_bak"
else
  echo "! Нет .git — синхронизация архивом с GitHub"
  sync_from_github_tar
  if command -v git >/dev/null 2>&1; then
    init_git_clean
  fi
fi

if [[ ! -f scripts/tbank-on-server-setup.sh ]]; then
  echo "Ошибка: после синхронизации нет scripts/tbank-on-server-setup.sh"
  exit 1
fi

SKIP_GIT_PULL=1 bash scripts/tbank-on-server-setup.sh
