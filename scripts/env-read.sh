#!/usr/bin/env bash
# Безопасное чтение KEY=VALUE из .env (без source — пароли с $ не ломают set -u).
env_get() {
  local key="$1"
  local file="${2:-${ENV_FILE:-}}"
  local line val
  [[ -n "$file" && -f "$file" ]] || return 1
  line=$(
    grep -E "^[[:space:]]*(export[[:space:]]+)?${key}[[:space:]]*=" "$file" 2>/dev/null | head -1
  ) || return 1
  val="${line#*=}"
  val="$(printf '%s' "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//;s/\r$//')"
  if [[ "${#val}" -ge 2 ]]; then
    if [[ "${val:0:1}" == '"' && "${val: -1}" == '"' ]]; then
      val="${val:1:-1}"
    elif [[ "${val:0:1}" == "'" && "${val: -1}" == "'" ]]; then
      val="${val:1:-1}"
    fi
  fi
  [[ -n "$val" ]] || return 1
  printf '%s' "$val"
}
