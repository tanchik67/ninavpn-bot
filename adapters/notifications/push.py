from __future__ import annotations

import logging

from core.domain.enums import NotificationChannel
from core.ports.notifications import NotificationMessage

log = logging.getLogger(__name__)


class PushNotifier:
    """Expo Push stub — Phase 2."""

    channel = NotificationChannel.PUSH

    async def send(self, message: NotificationMessage) -> bool:
        log.info(
            "PushNotifier stub: to=%s template=%s payload=%s",
            message.recipient,
            message.template,
            message.payload,
        )
        return True
