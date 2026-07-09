#!/usr/bin/env bash
# Подсказка для whitelist тестовой среды Т-Банка (403 на Init).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/env-read.sh
source "$ROOT/scripts/env-read.sh"

ENV_FILE="${ENV_FILE:-$ROOT/.env}"
tk="$(env_get TBANK_TERMINAL_KEY "$ENV_FILE" 2>/dev/null || true)"
out_ip="$(curl -4 -s --max-time 10 ifconfig.me 2>/dev/null || curl -4 -s --max-time 10 icanhazip.com 2>/dev/null || echo '???')"

echo "=== Whitelist для rest-api-test.tinkoff.ru ==="
echo
echo "Исходящий IP сервера (отправьте в Т-Банк): $out_ip"
echo "TerminalKey: ${tk:-не задан в .env}"
echo
echo "Письмо: acq_help@tinkoff.ru"
echo "Тема: Добавление IP в whitelist тестовой среды эквайринга"
echo
cat <<EOF
Добрый день!

Прошу добавить IP в whitelist тестовой среды интернет-эквайринга.

ИНН: <ваш ИНН>
Организация: <название>
IP-адрес: $out_ip
URL тестовой среды: rest-api-test.tinkoff.ru
TerminalKey: ${tk:-<DEMO TerminalKey>}

Запросы Init идут с сервера оплаты VPN-сервиса ninavpn.store.

Спасибо!
EOF
