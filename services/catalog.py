"""
Динамический каталог тарифов из БД (plan_tariffs) с fallback на config.PLANS.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple, Optional

from sqlalchemy import select

from config import PLANS as BUILTIN_PLANS
from database import AsyncSessionLocal, PlanTariff


_CATALOG_CACHE: Optional[Tuple[Dict[str, Any], float]] = None
_CACHE_TTL_SEC = 20.0


def invalidate_catalog_cache() -> None:
    global _CATALOG_CACHE
    _CATALOG_CACHE = None


def _row_to_plan_dict(row: PlanTariff) -> dict:
    return {
        "name": row.name,
        "months": int(row.months),
        "devices": int(row.devices),
        "price_rub": float(row.price_rub),
        "price_usdt": float(row.price_usdt),
        "description": row.description or "",
        "emoji": row.emoji or "📦",
        "popular": bool(row.popular),
    }


async def get_plans_catalog() -> Dict[str, Any]:
    """Если в БД есть активные тарифы — только они; иначе встроенные PLANS из config."""
    global _CATALOG_CACHE
    now = time.monotonic()
    if _CATALOG_CACHE and (now - _CATALOG_CACHE[1]) < _CACHE_TTL_SEC:
        return _CATALOG_CACHE[0]

    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(PlanTariff)
                .where(PlanTariff.is_active == True)
                .order_by(PlanTariff.sort_order.asc(), PlanTariff.plan_key.asc())
            )
        ).scalars().all()

    if rows:
        out = {r.plan_key: _row_to_plan_dict(r) for r in rows}
    else:
        out = dict(BUILTIN_PLANS)

    _CATALOG_CACHE = (out, now)
    return out


async def get_payment_method_entries() -> List[Tuple[str, dict]]:
    from config import payment_method_entries

    return payment_method_entries()
