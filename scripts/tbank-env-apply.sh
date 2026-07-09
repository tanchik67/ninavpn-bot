#!/usr/bin/env bash
# Обновляет /opt/ninavpn-bot/.env для эквайринга Т-Банка (только на сервере).
#
#   ./scripts/tbank-env-apply.sh
#   # или явно:
#   TBANK_TERMINAL_KEY=... TBANK_PASSWORD=... ./scripts/tbank-env-apply.sh
#
# Опционально: TBANK_TEST_MODE=1, ENV_FILE=/path/to/.env

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$(cd "$SCRIPT_DIR/.." && pwd)/.env}"

# shellcheck source=scripts/env-read.sh
source "$SCRIPT_DIR/env-read.sh"

if [[ -z "${TBANK_TERMINAL_KEY:-}" ]]; then
  TBANK_TERMINAL_KEY="$(env_get TBANK_TERMINAL_KEY "$ENV_FILE" || true)"
fi
if [[ -z "${TBANK_PASSWORD:-}" ]]; then
  TBANK_PASSWORD="$(env_get TBANK_PASSWORD "$ENV_FILE" || true)"
fi

if [[ -z "${TBANK_TERMINAL_KEY:-}" || -z "${TBANK_PASSWORD:-}" ]]; then
  echo "Ошибка: в $ENV_FILE нужны TBANK_TERMINAL_KEY и TBANK_PASSWORD."
  echo "Проверка:"
  echo "  grep '^TBANK_' $ENV_FILE | sed 's/TBANK_PASSWORD=.*/TBANK_PASSWORD=***/'"
  exit 1
fi

touch "$ENV_FILE"
chmod 600 "$ENV_FILE" 2>/dev/null || true

set_kv() {
  local key="$1"
  local val="$2"
  local tmp
  tmp=$(mktemp)
  if [[ -f "$ENV_FILE" ]]; then
    grep -v "^${key}=" "$ENV_FILE" > "$tmp" || true
  else
    : > "$tmp"
  fi
  printf '%s=%s\n' "$key" "$val" >> "$tmp"
  mv "$tmp" "$ENV_FILE"
  chmod 600 "$ENV_FILE" 2>/dev/null || true
}

set_kv "TBANK_TERMINAL_KEY" "$TBANK_TERMINAL_KEY"
set_kv "TBANK_PASSWORD" "$TBANK_PASSWORD"

test_mode="${TBANK_TEST_MODE:-}"
if [[ -z "$test_mode" ]]; then
  if [[ "$TBANK_TERMINAL_KEY" == *DEMO* ]]; then
    test_mode=1
  else
    test_mode=0
  fi
fi

verify_ssl="${TBANK_VERIFY_SSL:-}"
if [[ -z "$verify_ssl" ]]; then
  if [[ "$test_mode" == "1" ]]; then
    verify_ssl=false
  else
    verify_ssl=true
  fi
fi

set_kv "TBANK_TEST_MODE" "$test_mode"
set_kv "TBANK_VERIFY_SSL" "$verify_ssl"
set_kv "PAYMENT_PUBLIC_BASE_URL" "${PAYMENT_PUBLIC_BASE_URL:-https://ninavpn.store}"
set_kv "SBER_PBPN_URL" ""
set_kv "SBER_PBPN_APPEND_AMOUNT" "0"

echo "Обновлено: $ENV_FILE"
grep -E '^TBANK_|^PAYMENT_PUBLIC' "$ENV_FILE" | sed 's/TBANK_PASSWORD=.*/TBANK_PASSWORD=***/'
echo "Перезапуск: sudo systemctl restart ninavpn-bot"
echo "Проверка:   ./scripts/tbank-setup-check.sh"
