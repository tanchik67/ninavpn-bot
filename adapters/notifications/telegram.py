from __future__ import annotations

import logging
import tempfile
from pathlib import Path

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
        photo_path = message.payload.get("photo_path")
        if photo_path:
            # Document keeps pixels; WebP documents look like stickers in Telegram.
            ok = await self._send_support_image(
                chat_id, str(photo_path), str(text or "")
            )
            if ok:
                return True

        return await self._send_text(chat_id, str(text or ""))

    async def _send_text(self, chat_id: int, text: str) -> bool:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            if r.status_code >= 400:
                log.warning(
                    "Telegram HTML send failed: %s %s; retry plain",
                    r.status_code,
                    r.text[:200],
                )
                r2 = await client.post(
                    url,
                    json={"chat_id": chat_id, "text": text},
                )
                if r2.status_code >= 400:
                    log.warning(
                        "Telegram send failed: %s %s",
                        r2.status_code,
                        r2.text[:300],
                    )
                    return False
            return True

    async def _send_support_image(
        self, chat_id: int, photo_path: str, caption: str
    ) -> bool:
        path = Path(photo_path)
        if not path.is_file():
            log.warning("TelegramNotifier: photo missing %s", photo_path)
            return False

        prepared: Path | None = None
        try:
            send_path, filename, mime = self._as_jpeg_document(path)
            if send_path != path:
                prepared = send_path
            cap = (caption or "")[:1000]
            if await self._send_document(chat_id, send_path, filename, mime, cap):
                return True
            return await self._send_photo(chat_id, send_path, cap)
        finally:
            if prepared is not None:
                try:
                    prepared.unlink(missing_ok=True)
                except OSError:
                    pass

    def _as_jpeg_document(self, path: Path) -> tuple[Path, str, str]:
        """
        Always deliver a .jpg document. Raw .webp is shown by Telegram like a sticker.
        """
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return path, "screenshot.jpg", "image/jpeg"
        try:
            from PIL import Image

            with Image.open(path) as im:
                rgb = im.convert("RGB")
                tmp = tempfile.NamedTemporaryFile(
                    prefix="nvpn-support-", suffix=".jpg", delete=False
                )
                tmp_path = Path(tmp.name)
                tmp.close()
                rgb.save(tmp_path, format="JPEG", quality=92, optimize=True)
                return tmp_path, "screenshot.jpg", "image/jpeg"
        except Exception:
            log.exception("TelegramNotifier: jpeg convert failed, using original")
            mime = {
                ".png": "image/png",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }.get(suffix, "image/jpeg")
            return path, f"screenshot{suffix or '.jpg'}", mime

    async def _send_document(
        self,
        chat_id: int,
        file_path: Path,
        filename: str,
        mime: str,
        caption: str,
    ) -> bool:
        url = f"https://api.telegram.org/bot{self._token}/sendDocument"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                with file_path.open("rb") as fh:
                    r = await client.post(
                        url,
                        data={"chat_id": str(chat_id), "caption": caption},
                        files={"document": (filename, fh, mime)},
                    )
                if r.status_code >= 400:
                    log.warning(
                        "Telegram sendDocument failed: %s %s",
                        r.status_code,
                        r.text[:300],
                    )
                    return False
                return True
        except Exception:
            log.exception("Telegram sendDocument error")
            return False

    async def _send_photo(self, chat_id: int, photo_path: Path, caption: str) -> bool:
        url = f"https://api.telegram.org/bot{self._token}/sendPhoto"
        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                with photo_path.open("rb") as fh:
                    r = await client.post(
                        url,
                        data={"chat_id": str(chat_id), "caption": caption},
                        files={"photo": ("screenshot.jpg", fh, "image/jpeg")},
                    )
                if r.status_code >= 400:
                    log.warning(
                        "Telegram sendPhoto failed: %s %s",
                        r.status_code,
                        r.text[:300],
                    )
                    return False
                return True
        except Exception:
            log.exception("Telegram sendPhoto error")
            return False
