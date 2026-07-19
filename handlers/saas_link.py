"""Glue: link Telegram account to SaaS cabinet via one-time Redis code."""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

log = logging.getLogger(__name__)
router = Router()


@router.message(Command("linkcabinet"))
async def cmd_link_cabinet(message: Message) -> None:
    if not message.from_user:
        return
    try:
        from services.saas_bridge import create_telegram_link_code

        code = await create_telegram_link_code(message.from_user.id)
    except Exception:
        log.exception("linkcabinet failed")
        await message.answer(
            "Не удалось создать код привязки. Проверьте, что Redis запущен (REDIS_URL)."
        )
        return
    await message.answer(
        "🔗 Привязка к кабинету NinaVPN\n\n"
        f"Ваш код: <code>{code}</code>\n"
        f"Telegram ID: <code>{message.from_user.id}</code>\n\n"
        "В приложении вызовите привязку с этими данными "
        "(POST /api/v1/auth/link-telegram). Код действует 10 минут.",
        parse_mode="HTML",
    )
