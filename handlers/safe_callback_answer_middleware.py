"""
CallbackAnswerMiddleware с ответом до обработчика (pre=True) и без падения на просроченном callback.
"""
import logging
from typing import Any, Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from aiogram.utils.callback_answer import CallbackAnswer, CallbackAnswerMiddleware

log = logging.getLogger(__name__)


def _is_stale_callback_error(exc: TelegramBadRequest) -> bool:
    m = (exc.message or "").lower()
    return "query is too old" in m or "query id is invalid" in m


class SafeCallbackAnswerMiddleware(CallbackAnswerMiddleware):
    """
    По умолчанию отвечает на callback до handler — иначе при долгих операциях
    Telegram возвращает «query is too old».
    """

    def __init__(
        self,
        pre: bool = True,
        text: Optional[str] = None,
        show_alert: Optional[bool] = None,
        url: Optional[str] = None,
        cache_time: Optional[int] = None,
    ) -> None:
        super().__init__(
            pre=pre,
            text=text,
            show_alert=show_alert,
            url=url,
            cache_time=cache_time,
        )

    async def answer(
        self, event: CallbackQuery, callback_answer: CallbackAnswer
    ) -> Any:
        method = super().answer(event, callback_answer)
        try:
            return await method
        except TelegramBadRequest as e:
            if _is_stale_callback_error(e):
                log.warning("Callback answer skipped: %s", e.message)
                return None
            raise
