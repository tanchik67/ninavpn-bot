from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core.services.fx_display import format_price_bundle
from core.services.network_catalog import list_profiles
from core.services.network_locations import list_live_locations

router = APIRouter()


class LocationOut(BaseModel):
    id: str
    flag: str
    city: str
    country: str = ""
    region: str = ""
    protocol: str = "VLESS"
    protocols: list[str] = []
    status: str = "online"
    latency_ms: Optional[int] = None


class NetworkStatusOut(BaseModel):
    api: str = "ok"
    locations: list[LocationOut]
    profiles: list[dict[str, Any]]
    uptime_target: str = "99.9%"
    updated_hint: str = "Live 3x-ui panel pings; offline nodes hidden."


class FxRatesOut(BaseModel):
    sample_rub: float = 100
    prices: dict[str, float]
    note: str = "Display rates for UX; RUB rails and Stripe settle independently."


@router.get("/locations", response_model=list[LocationOut])
async def get_locations():
    # Include offline nodes so the cabinet list is never empty when panels
    # are misconfigured/unreachable; client shows status + latency.
    rows = await list_live_locations(hide_offline=False)
    return [
        LocationOut(
            id=str(loc["id"]),
            flag=str(loc.get("flag") or "🌐"),
            city=str(loc.get("city") or loc.get("label") or "Node"),
            country=str(loc.get("country") or ""),
            region=str(loc.get("region") or ""),
            protocol=str(loc.get("protocol") or "VLESS"),
            protocols=list(loc.get("protocols") or [])
            or [p.strip() for p in str(loc.get("protocol") or "VLESS").split("·") if p.strip()],
            status=str(loc.get("status") or "online"),
            latency_ms=loc.get("latency_ms"),
        )
        for loc in rows
    ]


@router.get("/status", response_model=NetworkStatusOut)
async def get_network_status():
    locations = await get_locations()
    return NetworkStatusOut(locations=locations, profiles=list_profiles())


@router.get("/profiles")
async def get_connection_profiles():
    return list_profiles()


@router.get("/fx", response_model=FxRatesOut)
async def get_fx_sample():
    return FxRatesOut(prices=format_price_bundle(100))
