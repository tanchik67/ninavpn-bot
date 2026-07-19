from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol


@dataclass
class ProvisionResult:
    uuid: Optional[str]
    links: list[str]
    subscription_url: Optional[str]
    expires_at: Optional[datetime] = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageResult:
    used_gb: float = 0.0
    status: str = "unknown"
    expire: Optional[datetime] = None
    raw: dict[str, Any] = field(default_factory=dict)


class VpnProvisioningPort(Protocol):
    async def provision(
        self,
        *,
        panel_user_key: int,
        months: int,
        devices: int,
        username: str | None = None,
    ) -> ProvisionResult: ...

    async def disable(self, panel_user_key: int) -> bool: ...

    async def usage(self, panel_user_key: int) -> UsageResult: ...

    async def extend_by_days(self, panel_user_key: int, days: int) -> bool: ...
