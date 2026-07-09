#!/usr/bin/env bash
# Переключение с тестового DEMO-терминала на боевой эквайринг.
# Запуск НА СЕРВЕРЕ:
#
#   TBANK_TERMINAL_KEY=боевой_ключ \
#   TBANK_PASSWORD=боевой_пароль \
#   ./scripts/tbank-prod-switch.sh
#
# Опционально: PAYMENT_PUBLIC_BASE_URL=https://ninavpn.store

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${TBANK_TERMINAL_KEY:-}" || -z "${TBANK_PASSWORD:-}" ]]; then
  echo "Задайте боевые TBANK_TERMINAL_KEY и TBANK_PASSWORD."
  exit 1
fi

if [[ "$TBANK_TERMINAL_KEY" == *DEMO* ]]; then
  echo "Ошибка: ключ содержит DEMO — это тестовый терминал."
  echo "Создайте боевой терминал в Т-Бизнес → Интернет-эквайринг."
  exit 1
fi

export TBANK_TEST_MODE=0
export TBANK_VERIFY_SSL="${TBANK_VERIFY_SSL:-true}"
export PAYMENT_PUBLIC_BASE_URL="${PAYMENT_PUBLIC_BASE_URL:-https://ninavpn.store}"

"$SCRIPT_DIR/tbank-env-apply.sh"

echo
echo "Боевой режим включён (TBANK_TEST_MODE=0)."
echo "В кабинете боевого терминала Notification URL:"
echo "  ${PAYMENT_PUBLIC_BASE_URL%/}/payment/tbank"
echo
echo "Перезапуск: sudo systemctl restart ninavpn-bot"
echo "Проверка:   ./scripts/tbank-setup-check.sh"
