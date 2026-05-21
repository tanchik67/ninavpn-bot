"""Проверка подписки на канал (CHANNEL_ID / CHANNEL_USERNAME) до обработки апдейтов."""
from __future__ import annotations

import logging
from html import escape as html_escape
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from config import admin_id_set, channel_subscribe_url, channel_subscription_target, settings
from utils.texts import txt_channel_required

log = logging.getLogger(__name__)

_SUBSCRIBED_STATUSES = frozenset(
    {
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.RESTRICTED,
    }
)


def _channel_html_label() -> str:
    u = (settings.CHANNEL_USERNAME or "").strip().lstrip("@")
    if u:
        return f"<b>@{html_escape(u)}</b>"
    return "<b>наш Telegram-канал</b>"


def _subscribe_keyboard() -> InlineKeyboardMarkup | None:
    url = channel_subscribe_url()
    if not url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📢 Подписаться", url=url)]]
    )


class ChannelSubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        target = channel_subscription_target()
        if target is None:
            return await handler(event, data)

        uid: int | None = None
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            uid = event.from_user.id
        if uid is None:
            return await handler(event, data)
        if uid in admin_id_set():
            return await handler(event, data)

        bot = data.get("bot")
        if bot is None:
            return await handler(event, data)

        try:
            member = await bot.get_chat_member(chat_id=target, user_id=uid)
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            log.warning(
                "Проверка подписки на канал: get_chat_member не выполнен (%s). "
                "Убедитесь, что бот — администратор канала.",
                e,
            )
            return await handler(event, data)

        if member.status in _SUBSCRIBED_STATUSES:
            return await handler(event, data)

        text = txt_channel_required(channel_html=_channel_html_label())
        kb = _subscribe_keyboard()

        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb)
            return None

        cb = event
        try:
            await cb.answer(
                "Сначала подпишись на канал — кнопка ниже в чате.",
                show_alert=True,
            )
        except Exception:
            pass
        if cb.message is not None:
            await cb.message.answer(text, reply_markup=kb)
        return None
