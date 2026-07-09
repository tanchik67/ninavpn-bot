#!/usr/bin/env bash
# Один раз: настроить GitHub Actions для деплоя на сервер.
# Требует: gh auth login (GitHub CLI).
#
#   ./scripts/github-deploy-bootstrap.sh
#
# Скрипт:
# 1. Кладёт SSH_PRIVATE_KEY, SSH_HOST, SSH_USER в secrets репозитория
# 2. Запускает workflow deploy.yml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if ! command -v gh >/dev/null 2>&1; then
  echo "Установите GitHub CLI: brew install gh"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Войдите в GitHub: gh auth login"
  exit 1
fi

SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
SSH_HOST="${SSH_HOST:-2.27.123.28}"
SSH_USER="${SSH_USER:-root}"
SSH_PORT="${SSH_PORT:-22}"

if [[ ! -f "$SSH_KEY" ]]; then
  echo "Нет SSH-ключа: $SSH_KEY"
  exit 1
fi

echo "→ secrets для $(gh repo view --json nameWithOwner -q .nameWithOwner)"
gh secret set SSH_PRIVATE_KEY < "$SSH_KEY"
gh secret set SSH_HOST -b "$SSH_HOST"
gh secret set SSH_USER -b "$SSH_USER"
gh secret set SSH_PORT -b "$SSH_PORT"

echo "→ запуск workflow Deploy to ninavpn.store"
gh workflow run deploy.yml

echo "Готово. Статус:"
gh run list --workflow=deploy.yml --limit 3
