"""
Клиент интернет-эквайринга Т-Банка (Tinkoff Acquiring API v2).
Документация: https://developer.tbank.ru/eacq/
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Any, Dict, Optional

import httpx

log = logging.getLogger(__name__)

# Вложенные объекты не участвуют в Token (Init и уведомления).
_TOKEN_SKIP_KEYS = frozenset({"Token", "Receipt", "DATA", "Data"})

TBANK_BASE_PROD = "https://securepay.tinkoff.ru/v2"
TBANK_BASE_TEST = "https://rest-api-test.tinkoff.ru/v2"


def acquiring_base_url(*, test_mode: bool, override: Optional[str] = None) -> str:
    o = (override or "").strip().rstrip("/")
    if o:
        return o
    return TBANK_BASE_TEST if test_mode else TBANK_BASE_PROD


def _scalar_to_token_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return str(value)
    return str(value)


def build_token(password: str, root_params: Dict[str, Any]) -> str:
    """SHA-256 по правилам Т-Банка: корневые поля без Token/Data/Receipt + Password."""
    pairs: list[tuple[str, str]] = []
    for key, val in root_params.items():
        if key in _TOKEN_SKIP_KEYS or key == "Token":
            continue
        if isinstance(val, (dict, list)):
            continue
        if val is None:
            continue
        pairs.append((key, _scalar_to_token_str(val)))
    pairs.append(("Password", password))
    pairs.sort(key=lambda x: x[0])
    concat = "".join(v for _, v in pairs)
    return hashlib.sha256(concat.encode("utf-8")).hexdigest()


def verify_notification_token(data: Dict[str, Any], password: str) -> bool:
    got = (data.get("Token") or "")
    if not isinstance(got, str) or not got.strip():
        return False
    expected = build_token(password, data)
    try:
        return secrets.compare_digest(got.strip().lower(), expected.lower())
    except Exception:
        return False


def order_id_for_payment(payment_id: int) -> str:
    """OrderId ≤ 36 символов, уникален на заказ."""
    return f"n{int(payment_id)}"


def parse_payment_id_from_order_id(order_id: str) -> Optional[int]:
    if not order_id or not isinstance(order_id, str):
        return None
    s = order_id.strip()
    if len(s) >= 2 and s[0] == "n" and s[1:].isdigit():
        return int(s[1:])
    return None


def rub_to_kopecks(amount_rub: float) -> int:
    return int(round(float(amount_rub) * 100))


async def init_payment(
    terminal_key: str,
    password: str,
    *,
    order_id: str,
    amount_kopecks: int,
    description: str,
    base_url: str,
    notification_url: Optional[str] = None,
    success_url: Optional[str] = None,
    fail_url: Optional[str] = None,
    verify_ssl: bool = True,
) -> Dict[str, Any]:
    """
    POST /Init. Возвращает распарсенный JSON (Success, PaymentURL, PaymentId, …).
    """
    body: Dict[str, Any] = {
        "TerminalKey": terminal_key,
        "Amount": int(amount_kopecks),
        "OrderId": order_id,
        "Description": (description or "NINAVPN")[:140],
        "PayType": "O",
    }
    if notification_url:
        body["NotificationURL"] = notification_url
    if success_url:
        body["SuccessURL"] = success_url
    if fail_url:
        body["FailURL"] = fail_url

    body["Token"] = build_token(password, body)
    url = f"{base_url.rstrip('/')}/Init"
    try:
        async with httpx.AsyncClient(timeout=45.0, verify=verify_ssl) as client:
            r = await client.post(url, json=body)
    except httpx.HTTPError as e:
        log.error("T-Bank Init: HTTP error %s url=%s verify_ssl=%s", e, url, verify_ssl)
        return {"Success": False, "Message": str(e), "http_status": 0}
    try:
        out = r.json()
    except Exception:
        log.error("T-Bank Init: не JSON, status=%s body=%s", r.status_code, r.text[:500])
        return {"Success": False, "Message": "invalid_json", "http_status": r.status_code}
    if not isinstance(out, dict):
        return {"Success": False, "Message": "invalid_response"}
    out["http_status"] = r.status_code
    return out


def notification_success_truthy(raw: Any) -> bool:
    if raw is True:
        return True
    if raw is False:
        return False
    s = str(raw).strip().lower()
    return s in ("true", "1", "yes")


def notification_error_ok(data: Dict[str, Any]) -> bool:
    code = data.get("ErrorCode")
    if code is None:
        return True
    try:
        return int(str(code)) == 0
    except ValueError:
        return False
