#!/usr/bin/env bash
# Выкладка лендинга site/ на ninavpn.store и обновление nginx.
#
#   cd /path/to/ninavpn-bot && ./scripts/deploy-site.sh
#
# Переменные (как в deploy-remote.sh):
#   REMOTE_HOST=2.27.123.28  REMOTE_USER=root  REMOTE_PATH=/opt/ninavpn-bot

set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-2.27.122.201}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_PATH="${REMOTE_PATH:-/opt/ninavpn-bot}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SITE_DIR="${ROOT}/site"
NGINX_CONF="${ROOT}/deploy/nginx/ninavpn.store.conf"

if [[ ! -f "${SITE_DIR}/index.html" ]]; then
  echo "Ошибка: нет ${SITE_DIR}/index.html"
  exit 1
fi

echo "→ site/ → ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/site/"
# shellcheck disable=SC2029
ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p ${REMOTE_PATH}/site"
# shellcheck disable=SC2029
scp "${SITE_DIR}/"*.html "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/site/"

echo "→ nginx ninavpn.store.conf"
# shellcheck disable=SC2029
scp "${NGINX_CONF}" "${REMOTE_USER}@${REMOTE_HOST}:/etc/nginx/sites-available/ninavpn.store"

echo "→ nginx -t && reload"
# shellcheck disable=SC2029
ssh "${REMOTE_USER}@${REMOTE_HOST}" "nginx -t && systemctl reload nginx"

echo ""
echo "Готово. Проверьте:"
echo "  https://ninavpn.store/"
echo "  https://ninavpn.store/ninavpn-oferta-2.html"
echo "  https://ninavpn.store/miniapp/  (Mini App по-прежнему через бота)"
