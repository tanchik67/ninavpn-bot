#!/usr/bin/env bash
# Lightweight uptime probe for NinaVPN API / site.
# Usage: BASE_URL=https://ninavpn.store ./scripts/health-monitor.sh
set -euo pipefail

BASE_URL="${BASE_URL:-https://ninavpn.store}"
FAIL=0

check() {
  local path="$1"
  local code
  code=$(curl -sS -o /tmp/nv_health_body -w "%{http_code}" --max-time 10 "${BASE_URL}${path}" || echo "000")
  if [[ "$code" != "200" ]]; then
    echo "FAIL ${path} → HTTP ${code}"
    FAIL=1
  else
    echo "OK   ${path} → HTTP ${code}"
  fi
}

check "/health"
check "/healthz"
check "/api/v1/network/locations"
check "/en/"
check "/status.html"

if [[ "$FAIL" -ne 0 ]]; then
  echo "health-monitor: unhealthy" >&2
  exit 1
fi
echo "health-monitor: healthy"
