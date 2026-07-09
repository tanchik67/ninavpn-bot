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

# shellcheck source=scripts/env-read.sh
source "$SCRIPT_DIR/env-read.sh"

git_sync_main() {
  local env_bak branch="${GIT_BRANCH:-main}"
  env_bak=$(mktemp)
  [[ -f .env ]] && cp .env "$env_bak"
  git fetch origin "$branch"
  git reset --hard "origin/${branch}"
  if [[ -s "$env_bak" ]]; then
    cp "$env_bak" .env
    chmod 600 .env 2>/dev/null || true
  fi
  rm -f "$env_bak"
}

echo "=== NINAVPN: настройка Т-Банк на сервере ==="
echo "Каталог: $ROOT"
echo

if [[ "${SKIP_GIT_PULL:-0}" != "1" ]] && [[ -d .git ]] && command -v git >/dev/null 2>&1; then
  echo "→ git fetch + reset --hard origin/main"
  if git_sync_main; then
    echo "✓ код синхронизирован с GitHub"
  else
    echo "! git sync не удался — продолжаем с текущим кодом"
  fi
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
  TBANK_TERMINAL_KEY="$(env_get TBANK_TERMINAL_KEY "$ENV_FILE" || true)"
  TBANK_PASSWORD="$(env_get TBANK_PASSWORD "$ENV_FILE" || true)"
  TBANK_TEST_MODE="$(env_get TBANK_TEST_MODE "$ENV_FILE" || true)"
  PAYMENT_PUBLIC_BASE_URL="$(env_get PAYMENT_PUBLIC_BASE_URL "$ENV_FILE" || true)"
  if [[ -z "$TBANK_TERMINAL_KEY" || -z "$TBANK_PASSWORD" ]]; then
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
