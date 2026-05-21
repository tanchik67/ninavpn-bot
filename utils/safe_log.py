"""
Безопасное логирование webhook-параметров: без подписей, паролей и лишних PII.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# Ключи, которые нельзя писать в логи (подписи, секреты)
_SENSITIVE_KEY_FRAGMENTS = (
    "sign",
    "secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "trbt-signature",
)


def _is_sensitive_key(key: str) -> bool:
    k = (key or "").lower()
    return any(frag in k for frag in _SENSITIVE_KEY_FRAGMENTS)


def sanitize_webhook_params(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Копия словаря для логов: без чувствительных ключей, длинные значения обрезаны."""
    if not data or not isinstance(data, dict):
        return {}
    out: Dict[str, Any] = {}
    for key, val in data.items():
        if _is_sensitive_key(str(key)):
            out[str(key)] = "<redacted>"
            continue
        s = str(val) if val is not None else ""
        if len(s) > 120:
            s = s[:117] + "..."
        out[str(key)] = s
    return out


def freekassa_log_summary(data: Optional[Dict[str, Any]], client_ip: str = "") -> str:
    """Краткая строка для IPN Freekassa."""
    d = data or {}
    return (
        f"ip={client_ip or '?'} "
        f"order={d.get('MERCHANT_ORDER_ID', '?')} "
        f"amount={d.get('AMOUNT', '?')} "
        f"merchant={d.get('MERCHANT_ID', '?')}"
    )
