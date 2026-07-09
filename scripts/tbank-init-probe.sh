#!/usr/bin/env bash
# Проверка Init API Т-Банка на сервере (без Telegram).
#   cd /opt/ninavpn-bot && source venv/bin/activate && bash scripts/tbank-init-probe.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=/dev/null
source venv/bin/activate 2>/dev/null || true

python3 << 'PY'
import asyncio
import json

from config import (
    settings,
    tbank_effective_test_mode,
    tbank_effective_verify_ssl,
    payment_public_base_url,
)
from services.tbank import acquiring_base_url, init_payment, order_id_for_payment

async def main():
    tk = (settings.TBANK_TERMINAL_KEY or "").strip()
    pw = (settings.TBANK_PASSWORD or "").strip()
    if not tk or not pw:
        print("FAIL: TBANK_TERMINAL_KEY или TBANK_PASSWORD пусты в .env")
        return 1
    test_mode = tbank_effective_test_mode()
    verify_ssl = tbank_effective_verify_ssl()
    base = acquiring_base_url(test_mode=test_mode, override=settings.TBANK_API_BASE)
    pub = payment_public_base_url()
    print(f"TerminalKey: {tk[:6]}...{tk[-4:] if len(tk) > 10 else tk}")
    print(f"test_mode={test_mode} verify_ssl={verify_ssl}")
    print(f"API base: {base}")
    print(f"PAYMENT_PUBLIC_BASE_URL: {pub or '(не задан)'}")
    resp = await init_payment(
        tk,
        pw,
        order_id=order_id_for_payment(999999),
        amount_kopecks=10000,
        description="NINAVPN probe",
        base_url=base,
        notification_url=f"{pub}/payment/tbank" if pub else None,
        success_url=f"{pub}/payment/success" if pub else None,
        fail_url=f"{pub}/payment/fail" if pub else None,
        verify_ssl=verify_ssl,
    )
    print("Response:", json.dumps(resp, ensure_ascii=False, indent=2))
    if resp.get("Success"):
        print("OK: Init прошёл, PaymentURL есть:", bool(resp.get("PaymentURL")))
        return 0
    print("FAIL: Init не прошёл — см. Message/Details выше")
    return 1

raise SystemExit(asyncio.run(main()))
PY
