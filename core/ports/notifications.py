from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from core.domain.enums import NotificationChannel


@dataclass
class NotificationMessage:
    channel: NotificationChannel
    template: str
    recipient: str
    subject: Optional[str] = None
    body: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


class Notifier(Protocol):
    channel: NotificationChannel

    async def send(self, message: NotificationMessage) -> bool: ...
