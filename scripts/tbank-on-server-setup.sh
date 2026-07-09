#!/usr/bin/env bash
# Полная настройка Т-Банка на прод-сервере (запускать НА СЕРВЕРЕ, не на Mac).
#
#   cd /opt/ninavpn-bot && bash scripts/tbank-on-server-setup.sh
#
# Если ключей ещё нет в .env:
#   TBANK_TERMINAL_KEY=... TBANK_PASSWORD=... bash scripts/tbank-on-server-setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

echo "=== NINAVPN: настройка Т-Банк на сервере ==="
echo "Каталог: $ROOT"
echo

if [[ -d .git ]] && command -v git >/dev/null 2>&1; then
  echo "→ git pull origin main"
  git pull origin main || echo "! git pull не удался — продолжаем с текущим кодом"
  echo
fi

if [[ -n "${TBANK_TERMINAL_KEY:-}" && -n "${TBANK_PASSWORD:-}" ]]; then
  TBANK_TEST_MODE="${TBANK_TEST_MODE:-}" PAYMENT_PUBLIC_BASE_URL="${PAYMENT_PUBLIC_BASE_URL:-}" \
    bash "$ROOT/scripts/tbank-env-apply.sh"
else
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Ошибка: нет $ENV_FILE"
    exit 1
  fi
  # shellcheck disable=SC1090
  set -a
  source <(grep -E '^(TBANK_|PAYMENT_PUBLIC|SBER_PBPN)' "$ENV_FILE" | sed 's/\r$//')
  set +a
  if [[ -z "${TBANK_TERMINAL_KEY:-}" || -z "${TBANK_PASSWORD:-}" ]]; then
    echo "Ошибка: задайте TBANK_TERMINAL_KEY и TBANK_PASSWORD в .env или в окружении."
    exit 1
  fi
  TBANK_TERMINAL_KEY="$TBANK_TERMINAL_KEY" TBANK_PASSWORD="$TBANK_PASSWORD" \
    TBANK_TEST_MODE="${TBANK_TEST_MODE:-}" PAYMENT_PUBLIC_BASE_URL="${PAYMENT_PUBLIC_BASE_URL:-}" \
    bash "$ROOT/scripts/tbank-env-apply.sh"
fi

echo
echo "→ перезапуск бота"
SKIP_PIP=1 bash "$ROOT/scripts/update-server.sh"
echo

echo "→ проверка"
bash "$ROOT/scripts/tbank-setup-check.sh"
echo
echo "В Т-Бизнес → тестовый терминал → Notification URL:"
echo "  https://ninavpn.store/payment/tbank"
echo "Тест: бот → тариф → Карта / СБП (Т-Банк)"
echo "Логи: journalctl -u ninavpn-bot -f | grep -i t-bank"
