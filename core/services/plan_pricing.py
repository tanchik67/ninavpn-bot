"""Site constructor pricing (ninavpn.store) — shared by SaaS checkout."""
from __future__ import annotations

from typing import Optional, Tuple

# Matches site/index.html constructor + config.EXTRA_DEVICE_PRICE
BASE_PRICES = {1: 100.0, 6: 500.0, 12: 1000.0}
BASE_DEVICES = {1: 1, 6: 3, 12: 5}
EXTRA_DEVICE_COST = {1: 70.0, 6: 280.0, 12: 490.0}


def calculate_price_rub(months: int, devices: int) -> float:
    m = int(months)
    d = max(1, min(10, int(devices)))
    if m not in BASE_PRICES:
        raise ValueError("invalid_months")
    base = BASE_PRICES[m]
    included = BASE_DEVICES[m]
    extra = max(0, d - included)
    return float(base + extra * EXTRA_DEVICE_COST[m])


def monthly_equivalent(total: float, months: int) -> int:
    return int(round(float(total) / max(1, int(months))))


def saving_vs_monthly(months: int, devices: int) -> Optional[float]:
    if months == 1:
        return None
    monthly = calculate_price_rub(1, devices)
    saved = monthly * months - calculate_price_rub(months, devices)
    return saved if saved > 0 else None


def custom_plan_key(months: int, devices: int) -> str:
    d = max(1, min(10, int(devices)))
    return f"custom_{int(months)}m_{d}d"


def resolve_plan_spec(
    *,
    plan_key: Optional[str] = None,
    months: Optional[int] = None,
    devices: Optional[int] = None,
) -> Tuple[str, int, int, float]:
    """Return (plan_key, months, devices, price_rub)."""
    if plan_key:
        key = plan_key.strip()
        if key.startswith("custom_"):
            segs = key.split("_")
            m = int(segs[1].replace("m", ""))
            d = max(1, min(10, int(segs[2].replace("d", ""))))
            if m not in BASE_PRICES:
                raise ValueError("invalid_months")
            return key, m, d, calculate_price_rub(m, d)
        # preset keys like 1m_1d — caller may still load from DB;
        # for pricing of known presets:
        presets = {
            "1m_1d": (1, 1),
            "6m_3d": (6, 3),
            "12m_5d": (12, 5),
        }
        if key in presets:
            m, d = presets[key]
            return key, m, d, calculate_price_rub(m, d)
        raise ValueError("plan_not_found")

    if months is None or devices is None:
        raise ValueError("plan_required")
    m = int(months)
    d = max(1, min(10, int(devices)))
    if m not in BASE_PRICES:
        raise ValueError("invalid_months")
    key = custom_plan_key(m, d)
    return key, m, d, calculate_price_rub(m, d)
