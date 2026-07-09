#!/usr/bin/env bash
# Безопасное чтение KEY=VALUE из .env (без source — пароли с $ не ломают set -u).
env_get() {
  local key="$1"
  local file="${2:-${ENV_FILE:-}}"
  local line
  [[ -n "$file" && -f "$file" ]] || return 1
  line=$(grep -E "^${key}=" "$file" 2>/dev/null | head -1) || return 1
  printf '%s' "${line#*=}" | sed 's/\r$//'
}
