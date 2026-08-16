#!/usr/bin/env bash
# Create Cloudflare DNS A record: app.ninavpn.store → origin IP (proxied).
#
#   export CF_API_TOKEN='...'   # Zone.DNS Edit on ninavpn.store
#   ./scripts/cloudflare-add-app-dns.sh
#
set -euo pipefail

ZONE_NAME="${ZONE_NAME:-ninavpn.store}"
RECORD_NAME="${RECORD_NAME:-app}"
ORIGIN_IP="${ORIGIN_IP:-2.27.122.201}"
CF_API="${CF_API:-https://api.cloudflare.com/client/v4}"

if [[ -z "${CF_API_TOKEN:-}" ]]; then
  echo "Нужен CF_API_TOKEN (Cloudflare → My Profile → API Tokens → Edit zone DNS)."
  echo "Затем:"
  echo "  export CF_API_TOKEN=..."
  echo "  ./scripts/cloudflare-add-app-dns.sh"
  exit 1
fi

auth=(-H "Authorization: Bearer ${CF_API_TOKEN}" -H "Content-Type: application/json")

zone_id=$(curl -fsS "${CF_API}/zones?name=${ZONE_NAME}" "${auth[@]}" \
  | python3 -c 'import sys,json; r=json.load(sys.stdin); print(r["result"][0]["id"] if r.get("result") else "")')
if [[ -z "$zone_id" ]]; then
  echo "Zone ${ZONE_NAME} не найдена или токен без доступа"
  exit 1
fi

fqdn="${RECORD_NAME}.${ZONE_NAME}"
existing=$(curl -fsS "${CF_API}/zones/${zone_id}/dns_records?type=A&name=${fqdn}" "${auth[@]}" \
  | python3 -c 'import sys,json; r=json.load(sys.stdin); print(r["result"][0]["id"] if r.get("result") else "")')

body=$(printf '{"type":"A","name":"%s","content":"%s","ttl":1,"proxied":true}' "$RECORD_NAME" "$ORIGIN_IP")

if [[ -n "$existing" ]]; then
  echo "→ update existing A ${fqdn}"
  curl -fsS -X PUT "${CF_API}/zones/${zone_id}/dns_records/${existing}" "${auth[@]}" --data "$body" >/dev/null
else
  echo "→ create A ${fqdn} → ${ORIGIN_IP} (proxied)"
  curl -fsS -X POST "${CF_API}/zones/${zone_id}/dns_records" "${auth[@]}" --data "$body" >/dev/null
fi

echo "OK: ${fqdn} → ${ORIGIN_IP} (proxied)"
dig +short "$fqdn" A || true
