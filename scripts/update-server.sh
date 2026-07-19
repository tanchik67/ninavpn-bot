#!/usr/bin/env bash
# Обновление NINAVPN на сервере после копирования кода (rsync/scp/git).
# Запуск:
#   cd /opt/ninavpn-bot && bash scripts/update-server.sh
# Опции окружения:
#   SKIP_PIP=1      — только перезапуск systemd, без pip install
#   SKIP_RESTART=1  — только pip, без systemctl
#   SKIP_SAAS=1     — не трогать API/worker (только бот)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# nginx (www-data) must traverse into ROOT to serve site/; keep .env private
if [[ "${EUID:-0}" -eq 0 ]]; then
  chmod 711 "$ROOT" 2>/dev/null || true
  if [[ -d "$ROOT/site" ]]; then
    chmod 755 "$ROOT/site" 2>/dev/null || true
    chmod 644 "$ROOT/site"/*.html 2>/dev/null || true
  fi
  chmod 600 "$ROOT/.env" 2>/dev/null || true
fi

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

_restart_unit() {
  local unit="$1"
  if [[ ! -f "/etc/systemd/system/${unit}.service" ]] && [[ ! -f "/lib/systemd/system/${unit}.service" ]]; then
    # Install unit from repo if present
    local src=""
    if [[ "$unit" == "ninavpn-bot" && -f "$ROOT/ninavpn-bot.service" ]]; then
      src="$ROOT/ninavpn-bot.service"
    elif [[ -f "$ROOT/deploy/systemd/${unit}.service" ]]; then
      src="$ROOT/deploy/systemd/${unit}.service"
    fi
    if [[ -n "$src" ]]; then
      cp "$src" "/etc/systemd/system/${unit}.service"
      systemctl daemon-reload
      systemctl enable "$unit" >/dev/null 2>&1 || true
      echo "→ installed systemd unit $unit"
    else
      echo "⚠ unit $unit not installed, skip"
      return 0
    fi
  fi
  systemctl restart "$unit"
  systemctl --no-pager --lines=5 status "$unit" || true
}

if [[ "${SKIP_RESTART:-0}" != "1" ]]; then
  if command -v systemctl >/dev/null 2>&1; then
    if [[ "${EUID:-0}" -ne 0 ]]; then
      echo "Нужен root для systemctl (или SKIP_RESTART=1)"
      exit 1
    fi
    _restart_unit ninavpn-bot
    if [[ "${SKIP_SAAS:-0}" != "1" ]]; then
      _restart_unit ninavpn-api || true
      _restart_unit ninavpn-worker || true
      # Soft health checks (do not fail update if SaaS not yet configured)
      curl -sf -o /dev/null -w "api /health %{http_code}\n" http://127.0.0.1:8000/health || echo "api /health unavailable"
    fi
  else
    echo "Предупреждение: systemctl не найден. Перезапустите процессы вручную."
  fi
fi

echo "Готово: $ROOT"
