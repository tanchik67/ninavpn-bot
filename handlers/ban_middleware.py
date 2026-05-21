from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from config import settings, admin_id_set
from database import AsyncSessionLocal, User


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        uid = None
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            uid = event.from_user.id
        if uid is None:
            return await handler(event, data)
        if uid in admin_id_set():
            return await handler(event, data)
        async with AsyncSessionLocal() as s:
            u = await s.scalar(select(User).where(User.tg_id == uid))
            if u and u.is_banned:
                if isinstance(event, Message):
                    await event.answer("⛔ Ваш доступ к боту ограничен.")
                else:
                    await event.answer("⛔ Доступ ограничен.", show_alert=True)
                return None
        return await handler(event, data)
