#!/usr/bin/env bash
# Проверка готовности оплаты через Т-Банк (эквайринг).
# Запуск: ./scripts/tbank-setup-check.sh
# На сервере: cd /opt/ninavpn-bot && ./scripts/tbank-setup-check.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok() { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}!${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; }

echo "=== NINAVPN: проверка Т-Банк (эквайринг) ==="
echo

# --- Чеклист Т-Бизнес (ручные шаги) ---
echo "Ручная настройка в Т-Бизнес (business.tbank.ru):"
echo "  1. Подключить интернет-эквайринг (не ссылку на перевод)"
echo "  2. Создать терминал → TerminalKey + Пароль для API"
echo "  3. Notification URL: https://ninavpn.store/payment/tbank"
echo "  4. Для тестов: TBANK_TEST_MODE=1 и тестовые ключи (developer.tbank.ru/eacq/)"
echo

# --- .env ---
if [[ ! -f "$ENV_FILE" ]]; then
  warn "Файл .env не найден: $ENV_FILE"
  warn "Скопируйте deploy/env/server.env.template → /opt/ninavpn-bot/.env"
else
  # shellcheck disable=SC1090
  set -a
  source <(grep -E '^(TBANK_|PAYMENT_PUBLIC|SBER_PBPN)' "$ENV_FILE" | sed 's/\r$//')
  set +a

  pub="${PAYMENT_PUBLIC_BASE_URL:-}"
  if [[ -n "$pub" ]]; then
    ok "PAYMENT_PUBLIC_BASE_URL=$pub"
  else
    fail "PAYMENT_PUBLIC_BASE_URL не задан — Init не передаст NotificationURL"
  fi

  tk="${TBANK_TERMINAL_KEY:-}"
  pw="${TBANK_PASSWORD:-}"
  if [[ -n "$tk" && -n "$pw" ]]; then
    ok "TBANK_TERMINAL_KEY и TBANK_PASSWORD заданы"
    if [[ "${TBANK_TEST_MODE:-0}" == "1" ]]; then
      warn "TBANK_TEST_MODE=1 (тестовый API)"
    else
      ok "TBANK_TEST_MODE=0 (боевой API)"
    fi
  else
    fail "Задайте TBANK_TERMINAL_KEY и TBANK_PASSWORD в .env"
  fi

  if [[ -n "${SBER_PBPN_URL:-}" ]]; then
    warn "SBER_PBPN_URL задан — в боте будет ручной «Перевод». Для только эквайринга оставьте пустым."
  else
    ok "SBER_PBPN_URL пуст — ручной перевод скрыт"
  fi
fi

echo

# --- Публичные URL ---
BASE="${PAYMENT_PUBLIC_BASE_URL:-https://ninavpn.store}"
BASE="${BASE%/}"

check_http() {
  local path="$1"
  local url="${BASE}${path}"
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 15 "$url" 2>/dev/null || echo "000")
  if [[ "$code" == "200" ]]; then
    ok "$url → HTTP $code"
  else
    fail "$url → HTTP $code (ожидался 200; бот/nginx на сервере?)"
  fi
}

echo "Проверка HTTP (домен: $BASE):"
check_http "/payment/success"
check_http "/payment/fail"
check_http "/healthz"

echo
echo "Webhook Т-Банка (POST только от Т-Банка, GET может вернуть 405):"
code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 15 -X POST \
  -H "Content-Type: application/json" \
  -d '{}' "${BASE}/payment/tbank" 2>/dev/null || echo "000")
if [[ "$code" == "403" || "$code" == "400" || "$code" == "200" ]]; then
  ok "${BASE}/payment/tbank → HTTP $code (маршрут доступен)"
else
  fail "${BASE}/payment/tbank → HTTP $code"
fi

echo
echo "Deep-link с сайта (после деплоя site/index.html):"
ok "t.me/ninavpn_bot?start=plan_1m_1d"
ok "t.me/ninavpn_bot?start=plan_6m_3d"
ok "t.me/ninavpn_bot?start=plan_12m_5d"
ok "t.me/ninavpn_bot?start=custom_6m_3d"

echo
echo "После заполнения .env: sudo systemctl restart ninavpn-bot"
echo "Логи webhook: journalctl -u ninavpn-bot -f | grep -i t-bank"
