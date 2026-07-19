"""Thin adapter over existing VpnPanel (3x-ui / Marzban)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from core.ports.vpn import ProvisionResult, UsageResult

log = logging.getLogger(__name__)


class XuiVpnAdapter:
    """Delegates to services.vpn_panel.get_vpn_panel()."""

    def __init__(self, panel=None) -> None:
        self._panel = panel

    def _get_panel(self):
        if self._panel is not None:
            return self._panel
        from services.vpn_panel import get_vpn_panel

        return get_vpn_panel()

    async def provision(
        self,
        *,
        panel_user_key: int,
        months: int,
        devices: int,
        username: str | None = None,
    ) -> ProvisionResult:
        panel = self._get_panel()
        result = await panel.create_or_extend_subscription(
            panel_user_key,
            months,
            devices,
            tg_username=username,
        )
        try:
            await panel.sync_device_limit(panel_user_key, devices)
        except Exception:
            log.warning("sync_device_limit failed for key=%s", panel_user_key, exc_info=True)

        expires: Optional[datetime] = None
        try:
            expires = await panel.get_subscription_expiry(panel_user_key)
        except Exception:
            log.warning("get_subscription_expiry failed for key=%s", panel_user_key, exc_info=True)
        if expires is None:
            expires = datetime.utcnow() + timedelta(days=30 * max(months, 1))

        links = [L for L in (result.get("links") or []) if L]
        sub_url = result.get("subscription_url")
        if not links and sub_url:
            links = [sub_url]

        return ProvisionResult(
            uuid=result.get("uuid"),
            links=links,
            subscription_url=sub_url,
            expires_at=expires,
            raw=result if isinstance(result, dict) else {},
        )

    async def disable(self, panel_user_key: int) -> bool:
        return await self._get_panel().disable_client(panel_user_key)

    async def usage(self, panel_user_key: int) -> UsageResult:
        raw = await self._get_panel().get_usage(panel_user_key)
        expire = raw.get("expire")
        if isinstance(expire, str):
            try:
                expire = datetime.fromisoformat(expire)
            except ValueError:
                expire = None
        return UsageResult(
            used_gb=float(raw.get("used_gb") or 0),
            status=str(raw.get("status") or "unknown"),
            expire=expire if isinstance(expire, datetime) else None,
            raw=raw if isinstance(raw, dict) else {},
        )

    async def extend_by_days(self, panel_user_key: int, days: int) -> bool:
        return await self._get_panel().extend_by_days(panel_user_key, days)


_adapter: Optional[XuiVpnAdapter] = None


def get_vpn_adapter() -> XuiVpnAdapter:
    global _adapter
    if _adapter is None:
        _adapter = XuiVpnAdapter()
    return _adapter
