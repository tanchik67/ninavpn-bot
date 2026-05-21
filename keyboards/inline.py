from typing import Any, Dict, List, Optional, Tuple

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import (
    PLANS,
    settings,
    payment_methods_visible,
    mini_app_configured,
    mini_app_url,
)


# ─── Главное меню ───────────────────────────────────────────
def kb_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🛒 Купить подписку",    callback_data="buy"))
    if mini_app_configured():
        b.row(
            InlineKeyboardButton(
                text="📱 Магазин (Mini App)",
                web_app=WebAppInfo(url=mini_app_url()),
            )
        )
    b.row(InlineKeyboardButton(text="📋 Мои подписки",       callback_data="my_subs"))
    b.row(InlineKeyboardButton(text="🌍 Серверы / статус",   callback_data="servers"))
    b.row(InlineKeyboardButton(text="🎁 Промокод",           callback_data="promo"),
          InlineKeyboardButton(text="👥 Реферал",            callback_data="referral"))
    b.row(InlineKeyboardButton(text="💬 Поддержка",          callback_data="support"))
    if settings.TERMS_URL and str(settings.TERMS_URL).strip():
        b.row(InlineKeyboardButton(text="📄 Условия", url=str(settings.TERMS_URL).strip()))
    return b.as_markup()


# ─── Выбор плана ────────────────────────────────────────────
def kb_plans(
    plans: Optional[Dict[str, Any]] = None,
) -> InlineKeyboardMarkup:
    catalog = plans if plans is not None else PLANS
    b = InlineKeyboardBuilder()
    for key, plan in catalog.items():
        popular = " ⭐" if plan.get("popular") else ""
        rub = float(plan["price_rub"])
        b.row(InlineKeyboardButton(
            text=f"{plan['emoji']} {plan['name']} — {rub:.0f} ₽{popular}",
            callback_data=f"plan:{key}",
        ))
    b.row(InlineKeyboardButton(text="🔧 Конструктор тарифа", callback_data="constructor"))
    b.row(InlineKeyboardButton(text="◀️ Назад",              callback_data="main"))
    return b.as_markup()


# ─── Конструктор: выбор срока ───────────────────────────────
def kb_constructor_period() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="1 мес",  callback_data="cp:1"),
        InlineKeyboardButton(text="6 мес",  callback_data="cp:6"),
        InlineKeyboardButton(text="12 мес", callback_data="cp:12"),
    )
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy"))
    return b.as_markup()


# ─── Конструктор: выбор устройств ───────────────────────────
def kb_constructor_devices(months: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    # Строки по 5 кнопок
    row1 = [InlineKeyboardButton(text=str(d), callback_data=f"cd:{months}:{d}") for d in range(1, 6)]
    row2 = [InlineKeyboardButton(text=str(d), callback_data=f"cd:{months}:{d}") for d in range(6, 11)]
    b.row(*row1)
    b.row(*row2)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="constructor"))
    return b.as_markup()


# ─── Выбор метода оплаты ────────────────────────────────────
def kb_payment_methods(
    plan_key: str,
    devices: int = 0,
    back_callback: Optional[str] = None,
    method_entries: Optional[List[Tuple[str, dict]]] = None,
) -> InlineKeyboardMarkup:
    """devices=0 означает стандартный план без конструктора.
    back_callback — иначе «Назад» ведёт на plan:{plan_key}."""
    b = InlineKeyboardBuilder()
    suffix = f":{devices}" if devices else ""
    entries = method_entries if method_entries is not None else payment_methods_visible()
    for method_key, method in entries:
        b.row(InlineKeyboardButton(
            text=method["name"],
            callback_data=f"pay:{method_key}:{plan_key}{suffix}",
        ))
    back = back_callback if back_callback is not None else f"plan:{plan_key}"
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back))
    return b.as_markup()


# ─── Подтверждение крипто-оплаты ────────────────────────────
def kb_crypto_confirm(payment_id: int, method: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="✅ Я оплатил — проверить",
        callback_data=f"check:{payment_id}:{method}",
    ))
    b.row(InlineKeyboardButton(
        text="🔄 Проверить ещё раз",
        callback_data=f"check:{payment_id}:{method}",
    ))
    b.row(InlineKeyboardButton(text="◀️ Изменить способ", callback_data=f"buy"))
    return b.as_markup()


# ─── После выдачи конфига ───────────────────────────────────
def kb_after_config() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📱 Как подключить?",   callback_data="howto"))
    b.row(InlineKeyboardButton(text="📋 Мои подписки",      callback_data="my_subs"))
    b.row(InlineKeyboardButton(text="🏠 Главное меню",      callback_data="main"))
    return b.as_markup()


# ─── Мои подписки ───────────────────────────────────────────
def kb_sub_actions(sub_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔄 Получить конфиг",   callback_data=f"getconf:{sub_id}"))
    b.row(InlineKeyboardButton(text="📊 Статистика трафика", callback_data=f"stat:{sub_id}"))
    b.row(InlineKeyboardButton(text="➕ Продлить",           callback_data=f"renew:{sub_id}"))
    b.row(InlineKeyboardButton(text="📜 История покупок",   callback_data="my_subs_hist"))
    b.row(InlineKeyboardButton(text="◀️ Назад",             callback_data="my_subs"))
    return b.as_markup()


# ─── Серверы ────────────────────────────────────────────────
def kb_servers_back() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main"))
    return b.as_markup()


# ─── Поддержка ──────────────────────────────────────────────
def kb_support() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✈️ Написать в поддержку",
            callback_data="support:chat",
        )
    )
    b.row(InlineKeyboardButton(text="📣 Наш канал",            url="https://t.me/ninavpn_official"))
    b.row(InlineKeyboardButton(text="🌐 Сайт",                 url="https://ninavpn.store"))
    b.row(InlineKeyboardButton(text="◀️ Назад",               callback_data="main"))
    return b.as_markup()


# ─── Инструкции по подключению ──────────────────────────────
def kb_howto() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📱 iPhone / iPad",   callback_data="howto:ios"))
    b.row(InlineKeyboardButton(text="🤖 Android",          callback_data="howto:android"))
    b.row(InlineKeyboardButton(text="🖥 Windows",          callback_data="howto:windows"))
    b.row(InlineKeyboardButton(text="🍎 macOS",            callback_data="howto:macos"))
    b.row(InlineKeyboardButton(text="🏠 Главное меню",     callback_data="main"))
    return b.as_markup()


# ─── Перевод по ссылке (SBER_PBPN_URL) + уведомление админам ─
def kb_sber_pay(sber_url: str, payment_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🏦 Перейти к оплате в Т-Банке", url=sber_url))
    b.row(
        InlineKeyboardButton(
            text="✅ Я оплатил — сообщить админу",
            callback_data=f"sber_notify:{payment_id}",
        )
    )
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy"))
    return b.as_markup()


# ─── Адмнин: подтверждение ──────────────────────────────────
def kb_admin_confirm_payment(payment_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Подтвердить",  callback_data=f"adm_ok:{payment_id}"),
        InlineKeyboardButton(text="❌ Отклонить",    callback_data=f"adm_no:{payment_id}"),
    )
    return b.as_markup()
