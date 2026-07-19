from __future__ import annotations

import logging

import httpx

from core.domain.enums import NotificationChannel
from core.ports.notifications import NotificationMessage
from core.settings import saas_settings

log = logging.getLogger(__name__)


class TelegramNotifier:
    channel = NotificationChannel.TELEGRAM

    def __init__(self, bot_token: str | None = None) -> None:
        self._token = bot_token or saas_settings.BOT_TOKEN

    async def send(self, message: NotificationMessage) -> bool:
        if not self._token:
            log.warning("TelegramNotifier: BOT_TOKEN missing, skip")
            return False
        try:
            chat_id = int(message.recipient)
        except (TypeError, ValueError):
            log.warning("TelegramNotifier: invalid chat_id %s", message.recipient)
            return False
        text = message.body or message.payload.get("text") or message.template
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            if r.status_code >= 400:
                log.warning("Telegram send failed: %s %s", r.status_code, r.text[:300])
                return False
            return True
