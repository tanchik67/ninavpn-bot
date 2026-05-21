#!/usr/bin/env bash
# Выкладка проекта на прод-сервер и перезапуск бота.
# Запускать с машины, где настроен SSH (см. DEPLOY.md).
#
# По умолчанию копирование через tar по SSH — на сервере не нужен rsync
# (на минимальных VPS часто стоит только openssh-server).
#
#   cd /path/to/ninavpn-bot && ./scripts/deploy-remote.sh
#
# Переменные окружения:
#   REMOTE_HOST, REMOTE_USER, REMOTE_PATH — как раньше
#   SKIP_PIP=1 — на сервере только restart (см. update-server.sh)
#   USE_RSYNC=1 — использовать rsync (на сервере: apt install rsync)
#
# Если «Permission denied» по паролю — настройте ключ: ssh-copy-id root@2.27.123.28

set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-2.27.123.28}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_PATH="${REMOTE_PATH:-/opt/ninavpn-bot}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKIP_PIP="${SKIP_PIP:-0}"

RSYNC_REMOTE="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/"

sync_tar() {
  echo "→ tar+ssh → ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/"
  # shellcheck disable=SC2029
  ( cd "$ROOT" && tar czf - \
      --exclude='venv' \
      --exclude='__pycache__' \
      --exclude='.git' \
      --exclude='.env' \
      --exclude='*.db' \
      . ) | ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p ${REMOTE_PATH} && cd ${REMOTE_PATH} && tar xzf -"
}

sync_rsync() {
  echo "→ rsync → ${RSYNC_REMOTE}"
  rsync -avz \
    --exclude 'venv' \
    --exclude '__pycache__' \
    --exclude '*.db' \
    --exclude '.env' \
    --exclude '.git' \
    "${ROOT}/" "${RSYNC_REMOTE}"
}

if [[ "${USE_RSYNC:-0}" == "1" ]]; then
  sync_rsync
else
  sync_tar
fi

echo "→ remote: scripts/update-server.sh"
# shellcheck disable=SC2029
ssh "${REMOTE_USER}@${REMOTE_HOST}" "cd ${REMOTE_PATH} && SKIP_PIP=${SKIP_PIP} bash scripts/update-server.sh"

echo "Готово."
