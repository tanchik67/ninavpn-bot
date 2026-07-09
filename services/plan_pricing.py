"""Расчёт тарифов для сайта и бота (единый источник)."""
from __future__ import annotations

from typing import Optional, Tuple

from config import EXTRA_DEVICE_PRICE, EXTRA_DEVICE_USDT, PLANS
from services.catalog import get_plans_catalog


def calc_custom_price_rub_usdt(months: int, devices: int) -> tuple[float, float]:
    """Как на лендинге ninavpn.store — не зависит от plan_tariffs в БД."""
    base = {
        1: {
            "price_rub": PLANS["1m_1d"]["price_rub"],
            "price_usdt": PLANS["1m_1d"]["price_usdt"],
            "devices": 1,
        },
        6: {
            "price_rub": PLANS["6m_3d"]["price_rub"],
            "price_usdt": PLANS["6m_3d"]["price_usdt"],
            "devices": 3,
        },
        12: {
            "price_rub": PLANS["12m_5d"]["price_rub"],
            "price_usdt": PLANS["12m_5d"]["price_usdt"],
            "devices": 5,
        },
    }[months]
    base_rub = float(base["price_rub"])
    base_usdt = float(base["price_usdt"])
    base_dev = int(base["devices"])
    extra = max(0, devices - base_dev)
    rub = base_rub + extra * EXTRA_DEVICE_PRICE[months]
    usdt = base_usdt + extra * EXTRA_DEVICE_USDT[months]
    return round(rub, 2), round(usdt, 2)


def months_from_plan_key(plan_key: str, *, plan_months: Optional[int] = None) -> int:
    if plan_key.startswith("custom_"):
        return int(plan_key.split("_")[1].replace("m", ""))
    if plan_months is not None:
        return int(plan_months)
    return int(PLANS.get(plan_key, {}).get("months", 1))


async def resolve_checkout_plan(
    *,
    plan_key: Optional[str] = None,
    months: Optional[int] = None,
    devices: Optional[int] = None,
) -> Tuple[str, int, int, float]:
    """
    Возвращает (plan_key, months, devices, price_rub).
    Либо plan_key, либо пара months+devices.
    """
    if plan_key:
        key = plan_key.strip()
        if key.startswith("custom_"):
            segs = key.split("_")
            m = int(segs[1].replace("m", ""))
            d = max(1, min(10, int(segs[2].replace("d", ""))))
            if m not in (1, 6, 12):
                raise ValueError("invalid_months")
            rub, _ = calc_custom_price_rub_usdt(m, d)
            return key, m, d, rub
        plans = await get_plans_catalog()
        if key not in plans:
            raise ValueError("plan_not_found")
        plan = plans[key]
        m = int(plan["months"])
        d = max(1, min(10, int(plan["devices"])))
        rub = float(plan["price_rub"])
        return key, m, d, rub

    if months is None or devices is None:
        raise ValueError("plan_required")
    m = int(months)
    d = max(1, min(10, int(devices)))
    if m not in (1, 6, 12):
        raise ValueError("invalid_months")
    key = f"custom_{m}m_{d}d"
    rub, _ = calc_custom_price_rub_usdt(m, d)
    return key, m, d, rub
