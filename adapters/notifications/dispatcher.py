from __future__ import annotations

import logging
from typing import Iterable

from adapters.notifications.email import EmailNotifier
from adapters.notifications.push import PushNotifier
from adapters.notifications.telegram import TelegramNotifier
from core.domain.enums import NotificationChannel
from core.ports.notifications import NotificationMessage, Notifier

log = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(self, notifiers: Iterable[Notifier] | None = None) -> None:
        self._by_channel: dict[NotificationChannel, Notifier] = {}
        for n in notifiers or [TelegramNotifier(), EmailNotifier(), PushNotifier()]:
            self._by_channel[n.channel] = n

    async def dispatch(self, message: NotificationMessage) -> bool:
        notifier = self._by_channel.get(message.channel)
        if not notifier:
            log.warning("No notifier for channel %s", message.channel)
            return False
        return await notifier.send(message)
