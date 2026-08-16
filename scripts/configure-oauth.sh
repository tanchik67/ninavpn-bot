#!/usr/bin/env bash
# Configure Google + Telegram OAuth on the API host and rebuild the Expo web app.
#
# Usage:
#   GOOGLE_WEB_CLIENT_ID='123-abc.apps.googleusercontent.com' ./scripts/configure-oauth.sh
#
# Telegram uses BOT_USERNAME from server .env (default NinaVPN_bot).
# BotFather Domain must already be: ninavpn.store
#
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-2.27.122.201}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_PATH="${REMOTE_PATH:-/opt/ninavpn-bot}"
GOOGLE_WEB_CLIENT_ID="${GOOGLE_WEB_CLIENT_ID:-}"
TELEGRAM_BOT_USERNAME="${TELEGRAM_BOT_USERNAME:-NinaVPN_bot}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -z "$GOOGLE_WEB_CLIENT_ID" ]]; then
  echo "Предупреждение: GOOGLE_WEB_CLIENT_ID не задан — Google-вход останется выключен."
  echo "  export GOOGLE_WEB_CLIENT_ID='….apps.googleusercontent.com'"
  echo "  $0"
fi

echo "→ patch API .env on ${REMOTE_USER}@${REMOTE_HOST}"
# shellcheck disable=SC2029
ssh "${REMOTE_USER}@${REMOTE_HOST}" bash -s <<EOF
set -euo pipefail
ENV="${REMOTE_PATH}/.env"
touch "\$ENV"
set_kv () {
  local k="\$1" v="\$2"
  if grep -q "^\$k=" "\$ENV" 2>/dev/null; then
    sed -i "s|^\$k=.*|\$k=\$v|" "\$ENV"
  else
    printf '%s=%s\n' "\$k" "\$v" >> "\$ENV"
  fi
}
set_kv TELEGRAM_BOT_USERNAME "${TELEGRAM_BOT_USERNAME}"
if [[ -n "${GOOGLE_WEB_CLIENT_ID}" ]]; then
  set_kv GOOGLE_CLIENT_IDS "${GOOGLE_WEB_CLIENT_ID}"
fi
# Prefer app origin for CORS (keep * if already intentional — only set if missing)
if ! grep -q '^API_CORS_ORIGINS=' "\$ENV"; then
  set_kv API_CORS_ORIGINS "https://app.ninavpn.store"
fi
systemctl restart ninavpn-api ninavpn-worker
systemctl is-active ninavpn-api
EOF

echo "→ deploy tg-login.html + google-login.html"
scp "${ROOT}/site/tg-login.html" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/site/tg-login.html"
scp "${ROOT}/site/google-login.html" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/site/google-login.html"

echo "→ write apps/client/.env and deploy app"
cat > "${ROOT}/apps/client/.env" <<ENVEOF
EXPO_PUBLIC_API_URL=https://ninavpn.store
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=${GOOGLE_WEB_CLIENT_ID}
EXPO_PUBLIC_TELEGRAM_BOT_USERNAME=${TELEGRAM_BOT_USERNAME}
EXPO_PUBLIC_TG_LOGIN_URL=https://ninavpn.store/tg-login.html
EXPO_PUBLIC_GOOGLE_LOGIN_URL=https://ninavpn.store/google-login.html
ENVEOF

# Keep app.json extra in sync for static export fallbacks
python3 - <<PY
import json
from pathlib import Path
p = Path("${ROOT}/apps/client/app.json")
data = json.loads(p.read_text())
extra = data.setdefault("expo", {}).setdefault("extra", {})
extra["apiUrl"] = "https://ninavpn.store"
extra["googleWebClientId"] = "${GOOGLE_WEB_CLIENT_ID}"
extra["telegramBotUsername"] = "${TELEGRAM_BOT_USERNAME}"
extra["tgLoginUrl"] = "https://ninavpn.store/tg-login.html"
extra["googleLoginUrl"] = "https://ninavpn.store/google-login.html"
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print("app.json extra updated")
PY

export EXPO_PUBLIC_API_URL=https://ninavpn.store
export EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID="${GOOGLE_WEB_CLIENT_ID}"
export EXPO_PUBLIC_TELEGRAM_BOT_USERNAME="${TELEGRAM_BOT_USERNAME}"
export EXPO_PUBLIC_TG_LOGIN_URL=https://ninavpn.store/tg-login.html
export EXPO_PUBLIC_GOOGLE_LOGIN_URL=https://ninavpn.store/google-login.html
SKIP_CERT=1 bash "${ROOT}/scripts/deploy-app.sh"

echo ""
echo "Готово."
echo "  Telegram: нужен Domain=ninavpn.store в BotFather для @${TELEGRAM_BOT_USERNAME}"
echo "  Google Web client → Authorized redirect URIs:"
echo "    https://ninavpn.store/google-login.html"
echo "    https://app.ninavpn.store"
echo "  Проверка: https://app.ninavpn.store  → Login → Google / Telegram"
