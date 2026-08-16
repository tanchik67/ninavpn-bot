#!/usr/bin/env bash
# Build Expo web client and publish to app.ninavpn.store
#
#   cd /path/to/ninavpn-bot && ./scripts/deploy-app.sh
#
# Env:
#   REMOTE_HOST REMOTE_USER REMOTE_PATH
#   SKIP_BUILD=1  — only rsync existing apps/client/dist
#   SKIP_CERT=1   — do not run certbot

set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-2.27.122.201}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_PATH="${REMOTE_PATH:-/opt/ninavpn-bot}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLIENT_DIR="${ROOT}/apps/client"
DIST_DIR="${CLIENT_DIR}/dist"
NGINX_CONF="${ROOT}/deploy/nginx/app.ninavpn.store.conf"

if [[ ! -f "${CLIENT_DIR}/package.json" ]]; then
  echo "Ошибка: нет ${CLIENT_DIR}/package.json"
  exit 1
fi

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "→ expo export --platform web"
  cd "${CLIENT_DIR}"
  # --clear: Metro otherwise may keep a stale embedded app.json (empty OAuth extras)
  EXPO_PUBLIC_API_URL="${EXPO_PUBLIC_API_URL:-https://ninavpn.store}" \
  EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID="${EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID:-}" \
  EXPO_PUBLIC_TELEGRAM_BOT_USERNAME="${EXPO_PUBLIC_TELEGRAM_BOT_USERNAME:-}" \
  EXPO_PUBLIC_TG_LOGIN_URL="${EXPO_PUBLIC_TG_LOGIN_URL:-https://ninavpn.store/tg-login.html}" \
    npx expo export --platform web --clear
fi

if [[ ! -f "${DIST_DIR}/index.html" ]]; then
  echo "Ошибка: нет ${DIST_DIR}/index.html — сначала соберите клиент"
  exit 1
fi

echo "→ dist → ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/apps/client/dist/"
# shellcheck disable=SC2029
ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p ${REMOTE_PATH}/apps/client/dist && chmod 711 ${REMOTE_PATH} ${REMOTE_PATH}/apps ${REMOTE_PATH}/apps/client || true"
rsync -avz --delete \
  --exclude '.DS_Store' \
  "${DIST_DIR}/" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/apps/client/dist/"

echo "→ nginx app.ninavpn.store.conf"
# Prefer HTTP-only vhost until cert exists (avoids nginx -t failure on missing PEM)
TMP_CONF=$(mktemp)
# shellcheck disable=SC2029
HAS_CERT=$(ssh "${REMOTE_USER}@${REMOTE_HOST}" "test -f /etc/letsencrypt/live/app.ninavpn.store/fullchain.pem && echo yes || echo no")
if [[ "$HAS_CERT" == "yes" ]]; then
  cp "${NGINX_CONF}" "${TMP_CONF}"
else
  # Strip the :443 server block until certbot succeeds
  awk '
    BEGIN { skip=0 }
    /^server \{/ { block++ }
    block==2 { next }
    { print }
  ' "${NGINX_CONF}" > "${TMP_CONF}"
fi
scp "${TMP_CONF}" "${REMOTE_USER}@${REMOTE_HOST}:/etc/nginx/sites-available/app.ninavpn.store"
rm -f "${TMP_CONF}"

# shellcheck disable=SC2029
ssh "${REMOTE_USER}@${REMOTE_HOST}" "ln -sf /etc/nginx/sites-available/app.ninavpn.store /etc/nginx/sites-enabled/app.ninavpn.store && nginx -t && systemctl reload nginx"

if [[ "${SKIP_CERT:-0}" != "1" ]]; then
  echo "→ certbot (если DNS уже указывает на сервер)"
  # shellcheck disable=SC2029
  ssh "${REMOTE_USER}@${REMOTE_HOST}" \
    "certbot --nginx -d app.ninavpn.store --non-interactive --agree-tos --register-unsafely-without-email --redirect 2>&1 || true"
  # Prefer app cert; fall back to panel cert (same vhost also serves panel.ninavpn.store)
  # shellcheck disable=SC2029
  if ssh "${REMOTE_USER}@${REMOTE_HOST}" "test -f /etc/letsencrypt/live/app.ninavpn.store/fullchain.pem"; then
    scp "${NGINX_CONF}" "${REMOTE_USER}@${REMOTE_HOST}:/etc/nginx/sites-available/app.ninavpn.store"
    # shellcheck disable=SC2029
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "sed -i 's#/etc/letsencrypt/live/panel.ninavpn.store/#/etc/letsencrypt/live/app.ninavpn.store/#g' /etc/nginx/sites-available/app.ninavpn.store; nginx -t && systemctl reload nginx"
  elif ssh "${REMOTE_USER}@${REMOTE_HOST}" "test -f /etc/letsencrypt/live/panel.ninavpn.store/fullchain.pem"; then
    scp "${NGINX_CONF}" "${REMOTE_USER}@${REMOTE_HOST}:/etc/nginx/sites-available/app.ninavpn.store"
    # shellcheck disable=SC2029
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "nginx -t && systemctl reload nginx"
  fi
fi

echo ""
echo "Готово. Проверьте:"
echo "  https://app.ninavpn.store/"
echo "  https://panel.ninavpn.store/  (алиас, если DNS app ещё нет)"
echo ""
echo "Если DNS app ещё не создан в Cloudflare:"
echo "  Type A  Name app  Content 2.27.122.201  Proxy ON (orange)"
echo "  или:  CF_API_TOKEN=... ./scripts/cloudflare-add-app-dns.sh"
