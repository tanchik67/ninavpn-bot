#!/usr/bin/env bash
# Обновление NINAVPN Bot на сервере после копирования кода (rsync/scp/git).
# Запуск:
#   cd /opt/ninavpn-bot && bash scripts/update-server.sh
# Опции окружения:
#   SKIP_PIP=1   — только перезапуск systemd, без pip install
#   SKIP_RESTART=1 — только pip, без systemctl (для отладки)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d venv ]]; then
  echo "Ошибка: нет каталога venv в $ROOT"
  echo "Один раз: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# shellcheck source=/dev/null
source venv/bin/activate

if [[ "${SKIP_PIP:-0}" != "1" ]]; then
  pip install --upgrade pip
  pip install -r requirements.txt
fi

if [[ "${SKIP_RESTART:-0}" != "1" ]]; then
  if command -v systemctl >/dev/null 2>&1; then
    if [[ "${EUID:-0}" -eq 0 ]]; then
      systemctl restart ninavpn-bot
      systemctl --no-pager status ninavpn-bot
    else
      sudo systemctl restart ninavpn-bot
      sudo systemctl --no-pager status ninavpn-bot
    fi
  else
    echo "Предупреждение: systemctl не найден. Перезапустите процесс бота вручную."
  fi
fi

echo "Готово: $ROOT"
