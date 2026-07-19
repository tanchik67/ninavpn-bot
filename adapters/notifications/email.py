from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from core.domain.enums import NotificationChannel
from core.ports.notifications import NotificationMessage
from core.settings import saas_settings

log = logging.getLogger(__name__)


class EmailNotifier:
    """SMTP stub — logs when SMTP not configured."""

    channel = NotificationChannel.EMAIL

    async def send(self, message: NotificationMessage) -> bool:
        if not saas_settings.SMTP_HOST or not saas_settings.SMTP_FROM:
            log.info(
                "EmailNotifier stub: to=%s subject=%s template=%s",
                message.recipient,
                message.subject,
                message.template,
            )
            return True

        msg = EmailMessage()
        msg["From"] = saas_settings.SMTP_FROM
        msg["To"] = message.recipient
        msg["Subject"] = message.subject or message.template
        msg.set_content(message.body or str(message.payload))

        try:
            with smtplib.SMTP(saas_settings.SMTP_HOST, saas_settings.SMTP_PORT, timeout=20) as smtp:
                smtp.starttls()
                if saas_settings.SMTP_USER:
                    smtp.login(saas_settings.SMTP_USER, saas_settings.SMTP_PASSWORD or "")
                smtp.send_message(msg)
            return True
        except Exception:
            log.exception("EmailNotifier send failed")
            return False
