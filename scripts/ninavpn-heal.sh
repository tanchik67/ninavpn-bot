#!/usr/bin/env bash
# «Лечение» NINAVPN Bot: venv + pip; на Linux ещё systemd.
#
# На сервере (Linux):
#   cd /opt/ninavpn-bot && bash scripts/ninavpn-heal.sh
#   bash scripts/ninavpn-heal.sh --recreate-venv   # если venv с Mac → Exec format error
#
# На Mac (локально): тот же скрипт пересоздаёт venv под macOS; проверка Mach-O только на Linux.
#
# Переменные:
#   NINAVPN_ROOT  — каталог бота (по умолчанию каталог репозитория относительно скрипта)
#   SKIP_SYSTEMD=1 — не трогать systemctl (только venv/pip)

set -euo pipefail

RECREATE_VENV=0
if [[ "${1:-}" == "--recreate-venv" ]]; then
  RECREATE_VENV=1
fi

ROOT="${NINAVPN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$ROOT"

echo "=== NINAVPN heal: $ROOT ==="

_sc() {
  if [[ "${EUID:-0}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

if [[ "${SKIP_SYSTEMD:-0}" != "1" ]] && command -v systemctl >/dev/null 2>&1; then
  echo "→ Останавливаю ninavpn-bot..."
  _sc systemctl stop ninavpn-bot 2>/dev/null || true
fi

if [[ "$RECREATE_VENV" -eq 1 ]]; then
  echo "→ Удаляю venv и создаю заново..."
  rm -rf venv
fi

if [[ ! -d venv ]]; then
  echo "→ Создаю venv: python3 -m venv venv"
  python3 -m venv venv
fi

PY="$ROOT/venv/bin/python"
# На Linux Mach-O = venv случайно с Mac → systemd: Exec format error. На Darwin Mach-O — норма.
if [[ "$(uname -s)" == "Linux" ]] && [[ -x "$PY" ]] && command -v file >/dev/null 2>&1; then
  FT=$(file -b "$PY" || true)
  echo "→ Проверка интерпретатора (Linux): $FT"
  if echo "$FT" | grep -qi 'mach-o'; then
    echo "ОШИБКА: в venv бинарник macOS (Mach-O). Удалите venv и запустите: $0 --recreate-venv"
    exit 1
  fi
fi

# shellcheck source=/dev/null
source venv/bin/activate
echo "→ pip install -r requirements.txt"
pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f .env ]]; then
  echo "Предупреждение: нет файла .env — скопируйте .env.example и заполните."
fi

if [[ "${SKIP_SYSTEMD:-0}" != "1" ]] && command -v systemctl >/dev/null 2>&1; then
  echo "→ Запускаю ninavpn-bot..."
  _sc systemctl start ninavpn-bot
  sleep 1
  _sc systemctl --no-pager status ninavpn-bot || true
  echo ""
  echo "Последние строки лога:"
  _sc journalctl -u ninavpn-bot -n 15 --no-pager
else
  echo "Перезапустите бота вручную: source venv/bin/activate && python3 main.py"
fi

echo ""
echo "=== Готово ==="
