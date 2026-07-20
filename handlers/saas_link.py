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
            "Не удалось создать код привязки.\n"
            "Напишите в поддержку или попробуйте позже."
        )
        return

    await message.answer(
        "🔗 <b>Привязка Telegram к кабинету</b>\n\n"
        f"1. Откройте приложение NinaVPN\n"
        f"2. Вкладка <b>Аккаунт</b> → «Привязать Telegram»\n"
        f"3. Введите код: <code>{code}</code>\n\n"
        f"Код действует <b>10 минут</b>.\n"
        f"Ваш Telegram ID: <code>{message.from_user.id}</code>\n\n"
        "После привязки сюда будут приходить уведомления "
        "о выдаче конфига и окончании подписки.",
        parse_mode="HTML",
    )
