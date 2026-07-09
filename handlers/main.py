"""
Все хэндлеры бота в одном файле для удобства.
"""
import asyncio
import base64
import functools
import inspect
import json
import logging
import re
from html import escape as html_escape
from typing import Optional
from datetime import datetime, timedelta
from io import BytesIO

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    BufferedInputFile, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from config import (
    settings,
    PLANS,
    EXTRA_DEVICE_PRICE,
    EXTRA_DEVICE_USDT,
    PAYMENT_METHODS,
    admin_id_set,
    sber_pbpn_configured,
    sber_pay_url,
    tbank_configured,
    tbank_effective_test_mode,
    tbank_effective_verify_ssl,
    payment_public_base_url,
    welcome_banner_path,
)
from database import (
    User,
    Subscription,
    Payment,
    PromoCode,
    PromoRedemption,
    PlanTariff,
    AsyncSessionLocal,
)
from services.catalog import (
    get_plans_catalog,
    get_payment_method_entries,
    invalidate_catalog_cache,
)
from keyboards.inline import (
    kb_main, kb_plans, kb_payment_methods, kb_crypto_confirm,
    kb_after_config, kb_sub_actions, kb_servers_back,
    kb_support, kb_howto, kb_admin_confirm_payment, kb_sber_pay,
    kb_constructor_period, kb_constructor_devices,
)
from services.vpn_panel import get_vpn_panel, client_email, legacy_client_email
from services.payment import (
    check_usdt_payment, check_ton_payment,
    rub_to_ton,
    verify_freekassa_webhook, get_ton_price_rub,
    unique_usdt_amount, unique_ton_amount,
)
from utils.texts import (
    txt_welcome, txt_plans, txt_plan_detail, txt_pay_usdt, txt_pay_ton,
    txt_pay_tbank, txt_pay_sber, txt_payment_checking, txt_payment_not_found,
    txt_config_ready, txt_my_subs_empty, txt_sub_info,
    txt_referral, txt_howto, txt_constructor_period,
    txt_constructor_devices, txt_constructor_result,
)

log = logging.getLogger(__name__)
router = Router()


class SupportStates(StatesGroup):
    """Ожидание сообщения пользователя для пересылки админам."""
    waiting_message = State()


async def cq_edit_message(
    cb: CallbackQuery,
    text: str,
    *,
    reply_markup=None,
    parse_mode: Optional[str] = "HTML",
) -> bool:
    """edit_text с учётом «message is not modified» и ошибок разбора HTML."""
    if cb.message is None:
        try:
            await cb.answer("Открой меню командой /start", show_alert=True)
        except Exception:
            pass
        return False
    try:
        await cb.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return True
        if "can't parse entities" in err or "parse entities" in err:
            log.warning("HTML в сообщении не принят Telegram, показываю без разметки: %s", e)
            plain = re.sub(r"<[^>]+>", "", text)
            try:
                await cb.message.edit_text(plain, reply_markup=reply_markup)
                return True
            except TelegramBadRequest as e2:
                log.warning("Повторное редактирование не удалось: %s", e2)
        log.warning("edit_text: %s", e)
        # Нельзя отредактировать (устаревшее сообщение, тип чата, Mini App) — дублируем текст новым сообщением
        try:
            await cb.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return True
        except TelegramBadRequest as e3:
            e3s = str(e3).lower()
            if "can't parse entities" in e3s or "parse entities" in e3s:
                plain = re.sub(r"<[^>]+>", "", text)
                try:
                    await cb.message.answer(plain, reply_markup=reply_markup)
                    return True
                except TelegramBadRequest:
                    pass
            log.warning("answer fallback после edit_text: %s", e3)
        try:
            await cb.answer("Не удалось показать оплату. Нажми /start или открой меню снова.", show_alert=True)
        except TelegramBadRequest:
            pass
        except Exception:
            pass
        return False


FREEKASSA_AMOUNT_TOLERANCE = 0.02


def parse_custom_start_param(raw: str) -> Optional[tuple[int, int]]:
    """Парсит deep link с сайта: custom_6m_3d или custom_6m_3d_500rub."""
    if not raw.startswith("custom_"):
        return None
    body = raw[7:]
    if body.endswith("rub"):
        idx = body.rfind("_")
        if idx > 0:
            tail = body[idx + 1 :]
            if tail.endswith("rub") and tail[:-3].isdigit():
                body = body[:idx]
    segs = body.split("_")
    if len(segs) < 2:
        return None
    try:
        months = int(segs[0].replace("m", ""))
        devices = int(segs[1].replace("d", ""))
    except ValueError:
        return None
    if months not in (1, 6, 12) or not (1 <= devices <= 10):
        return None
    return months, devices


async def _months_from_plan_key(plan_key: str) -> int:
    if plan_key.startswith("custom_"):
        return int(plan_key.split("_")[1].replace("m", ""))
    plans = await get_plans_catalog()
    return int(plans.get(plan_key, {}).get("months", 1))


async def _revert_payment_processing(payment_id: int) -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == "processing")
            .values(status="pending")
        )
        await s.commit()


# ══════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════

async def get_or_create_user(tg_id: int, username: str, full_name: str,
                              referrer_id: Optional[int] = None) -> User:
    async with AsyncSessionLocal() as s:
        user = await s.scalar(select(User).where(User.tg_id == tg_id))
        if user:
            changed = False
            username = (username or "").strip() or None
            full_name = (full_name or "").strip() or None
            if username and username != user.username:
                user.username = username
                changed = True
            if full_name and full_name != user.full_name:
                user.full_name = full_name
                changed = True

            # Реферала фиксируем только один раз и только до первой успешной оплаты приглашённого.
            if (
                referrer_id
                and not user.referrer_id
                and not user.ref_bonus_given
                and int(referrer_id) != int(tg_id)
            ):
                has_confirmed = await s.scalar(
                    select(func.count()).select_from(Payment).where(
                        Payment.user_tg_id == tg_id,
                        Payment.status == "confirmed",
                    )
                )
                if int(has_confirmed or 0) == 0:
                    user.referrer_id = int(referrer_id)
                    changed = True

            if changed:
                await s.commit()
            return user
        user = User(
            tg_id=tg_id,
            username=username,
            full_name=full_name,
            referrer_id=referrer_id,
        )
        s.add(user)
        try:
            await s.commit()
            await s.refresh(user)
        except IntegrityError:
            await s.rollback()
            user = await s.scalar(select(User).where(User.tg_id == tg_id))
            if not user:
                raise
    return user


async def sync_username_from_telegram(bot: Bot, tg_id: int) -> Optional[str]:
    """
    Актуальный @username из Telegram API (getChat) и запись в users.username.
    Нужен для отображения в «Моя подписка» и для логина в VPN-панели (username_<tg_id>).
    """
    try:
        chat = await bot.get_chat(tg_id)
        raw = getattr(chat, "username", None)
        if not raw:
            return None
        live = str(raw).strip().lstrip("@")
        if not live:
            return None
    except Exception:
        return None
    async with AsyncSessionLocal() as s:
        user = await s.scalar(select(User).where(User.tg_id == tg_id))
        if user and (user.username or "") != live:
            user.username = live
            await s.commit()
    return live


async def calc_custom_price(months: int, devices: int) -> tuple[float, float]:
    """Возвращает (rub, usdt) для конструктора."""
    # Конструктор должен совпадать с витриной (https://ninavpn.store) и не зависеть
    # от того, настроены ли тарифы в БД (plan_tariffs).
    base = {
        1:  {"price_rub": PLANS["1m_1d"]["price_rub"],  "price_usdt": PLANS["1m_1d"]["price_usdt"],  "devices": 1},
        6:  {"price_rub": PLANS["6m_3d"]["price_rub"],  "price_usdt": PLANS["6m_3d"]["price_usdt"],  "devices": 3},
        12: {"price_rub": PLANS["12m_5d"]["price_rub"], "price_usdt": PLANS["12m_5d"]["price_usdt"], "devices": 5},
    }[months]

    base_rub = float(base["price_rub"])
    base_usdt = float(base["price_usdt"])
    base_dev = int(base["devices"])
    extra     = max(0, devices - base_dev)
    rub  = base_rub  + extra * EXTRA_DEVICE_PRICE[months]
    usdt = base_usdt + extra * EXTRA_DEVICE_USDT[months]
    return round(rub, 2), round(usdt, 2)


async def send_config_ready_bundle(
    bot: Bot,
    chat_id: int,
    config_link: str,
    expires_str: str,
    devices: int,
    *,
    extra_link: Optional[str] = None,
    partial_nodes: bool = False,
    reply_markup=None,
) -> None:
    """HTML-инструкция + отдельные plain-сообщения со ссылками (удобно копировать в Telegram)."""
    await bot.send_message(
        chat_id,
        txt_config_ready(
            config_link,
            expires_str,
            devices,
            extra_link=extra_link,
            partial_nodes=partial_nodes,
        ),
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    main = (config_link or "").strip()
    if main and main != "—":
        await bot.send_message(
            chat_id,
            main,
            disable_web_page_preview=True,
        )
    extra = (extra_link or "").strip()
    if extra:
        await bot.send_message(
            chat_id,
            extra,
            disable_web_page_preview=True,
        )


async def _upsert_subscription_after_promo(
    s,
    tg_id: int,
    links: list[str],
    primary: str,
    expires_at: datetime,
    devices: int,
) -> None:
    """Обновить активную подписку или создать запись promo после выдачи дней по промокоду."""
    now = datetime.utcnow()
    devices = max(1, min(10, int(devices)))
    main = (primary or "").strip() or (links[0] if links else "")
    extra = links[1] if len(links) > 1 else None

    active = (
        await s.execute(
            select(Subscription).where(
                Subscription.user_tg_id == tg_id,
                Subscription.is_active == True,
                Subscription.expires_at != None,
                Subscription.expires_at > now,
            )
        )
    ).scalars().all()
    if active:
        sub = max(active, key=lambda x: x.expires_at or now)
        sub.expires_at = expires_at
        if main:
            sub.config_link = main
        if extra is not None:
            sub.config_link_extra = extra
        sub.devices = devices
    else:
        s.add(
            Subscription(
                user_tg_id=tg_id,
                plan_key="promo",
                devices=devices,
                months=0,
                price_paid=0.0,
                config_link=main,
                config_link_extra=extra,
                started_at=now,
                expires_at=expires_at,
                is_active=True,
            )
        )


async def issue_config(bot: Bot, tg_id: int, plan_key: str,
                        devices: int, months: int, price_rub: float,
                        payment_id: int):
    """Создаёт/продлевает клиента в панели VPN, сохраняет подписку, отправляет конфиг."""
    await sync_username_from_telegram(bot, tg_id)
    ref_pending = False
    referrer_id: Optional[int] = None

    async with AsyncSessionLocal() as s:
        user = await s.scalar(select(User).where(User.tg_id == tg_id))
        if user and user.referrer_id and not user.ref_bonus_given:
            ref_pending = True
            referrer_id = user.referrer_id

    panel = get_vpn_panel()
    try:
        result = await panel.create_or_extend_subscription(
            tg_id,
            months,
            devices,
            tg_username=(user.username if user else None),
        )
        if not await panel.sync_device_limit(tg_id, devices):
            log.warning(
                "sync_device_limit после выдачи не применился: tg_id=%s devices=%s",
                tg_id,
                devices,
            )
    except Exception as e:
        log.exception("VPN panel create_or_extend error")
        await bot.send_message(
            tg_id,
            "❌ Ошибка создания конфига. Укажите в обращении номер заказа: "
            f"<code>{payment_id}</code>.\n"
            "Напишите в поддержку: «Поддержка» → «Написать в поддержку».",
            parse_mode="HTML",
        )
        err_short = html_escape(str(e)[:800])
        alert = (
            f"🚨 <b>Ошибка VPN-панели</b>\n"
            f"user <code>{tg_id}</code> payment <code>{payment_id}</code>\n"
            f"email в панели (legacy): <code>{html_escape(legacy_client_email(tg_id))}</code>\n"
            f"email в панели (preferred): <code>{html_escape(client_email(tg_id, user.username if user else None))}</code>\n\n"
            f"<code>{err_short}</code>"
        )
        for aid in admin_id_set():
            try:
                await bot.send_message(aid, alert, parse_mode="HTML")
            except Exception as ex:
                log.warning("Не удалось уведомить админа %s: %s", aid, ex)
        return

    expires = await panel.get_subscription_expiry(tg_id)
    if expires is None:
        expires = datetime.utcnow() + timedelta(days=30 * months)

    links = [L for L in (result.get("links") or []) if L]
    if not links and result.get("subscription_url"):
        links = [result["subscription_url"]]
    link = links[0] if links else ""
    link_extra = links[1] if len(links) > 1 else None
    partial_nodes = bool(result.get("partial"))
    node_errors = result.get("node_errors") or []

    async with AsyncSessionLocal() as s:
        sub = Subscription(
            user_tg_id=tg_id,
            plan_key=plan_key,
            devices=devices,
            months=months,
            price_paid=price_rub,
            marzban_uuid=result.get("uuid"),
            config_link=link,
            config_link_extra=link_extra,
            started_at=datetime.utcnow(),
            expires_at=expires,
            is_active=True,
        )
        s.add(sub)

        await s.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status="confirmed", confirmed_at=datetime.utcnow())
        )

        await s.commit()

    expires_str = expires.strftime("%d.%m.%Y")
    await send_config_ready_bundle(
        bot,
        tg_id,
        link or "—",
        expires_str,
        devices,
        extra_link=link_extra,
        partial_nodes=partial_nodes,
        reply_markup=kb_after_config(),
    )

    for i, url in enumerate(links):
        if not url:
            continue
        try:
            qr_b64 = panel.make_qr_base64(url)
            qr_bytes = base64.b64decode(qr_b64)
            v = url.startswith("vless://")
            cap = (
                ("📱 QR — VLESS (основной)" if v else "📱 QR — основной")
                if i == 0
                else ("📱 QR — VLESS (запасной)" if v else "📱 QR — запасной")
            )
            await bot.send_photo(
                tg_id,
                BufferedInputFile(qr_bytes, filename=f"ninavpn_config_{i}.png"),
                caption=cap,
            )
        except Exception as e:
            log.warning(f"QR error: {e}")

    pay_method_key = ""
    async with AsyncSessionLocal() as s:
        prow = await s.scalar(select(Payment).where(Payment.id == payment_id))
        if prow and prow.method:
            pay_method_key = str(prow.method).strip()
    method_name = (
        PAYMENT_METHODS.get(pay_method_key, {}).get("name") if pay_method_key else None
    ) or pay_method_key or "—"

    admin_lines = [
        f"✅ <b>Новая подписка</b>",
        f"👤 user_id: <code>{tg_id}</code>",
        f"📦 Тариф: <code>{html_escape(plan_key)}</code> / {devices} уст. / {months} мес.",
        f"💰 {price_rub} ₽",
        f"💳 Оплата: {html_escape(method_name)}",
        f"🧾 Заказ: <code>{payment_id}</code>",
        f"🔑 Панель: <code>{html_escape(client_email(tg_id))}</code>",
        f"📅 До (по панели): {expires_str}",
    ]
    if partial_nodes and node_errors:
        admin_lines.append("⚠️ Частичный сбой узлов:")
        for ne in node_errors:
            admin_lines.append(f"  • {ne.get('label', '?')}: {ne.get('error', '')}")
    admin_html = "\n".join(admin_lines)
    for aid in admin_id_set():
        try:
            await bot.send_message(aid, admin_html, parse_mode="HTML")
        except Exception as e:
            log.warning("issue_config: не удалось уведомить админа %s: %s", aid, e)

    if ref_pending and referrer_id:
        ref_ok = await panel.extend_by_days(referrer_id, settings.REFERRAL_BONUS_DAYS)
        if ref_ok and int(getattr(settings, "REFERRAL_INVITEE_BONUS_DAYS", 0) or 0) > 0:
            inv_d = int(settings.REFERRAL_INVITEE_BONUS_DAYS)
            inv_ok = await panel.extend_by_days(tg_id, inv_d)
            if not inv_ok:
                log.warning(
                    "Referral invitee extend failed tg_id=%s +%s d", tg_id, inv_d
                )
        if ref_ok:
            async with AsyncSessionLocal() as s:
                u = await s.scalar(select(User).where(User.tg_id == tg_id))
                if u:
                    u.ref_bonus_given = True
                    await s.commit()
            await bot.send_message(
                referrer_id,
                f"🎁 Друг оплатил подписку в NINAVPN!\n"
                f"К твоему VPN добавлено <b>+{settings.REFERRAL_BONUS_DAYS}</b> дн.",
                parse_mode="HTML",
            )
        else:
            log.warning("Referral extend failed for referrer_id=%s", referrer_id)


# ══════════════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    referrer_id = None
    ref_bonus = False
    plan_from_mini: Optional[str] = None
    custom_from_site: Optional[tuple[int, int]] = None
    if len(args) > 1:
        raw = args[1].strip()
        if raw.startswith("ref"):
            try:
                referrer_id = int(raw[3:])
                if referrer_id == message.from_user.id:
                    referrer_id = None
                else:
                    ref_bonus = True
            except ValueError:
                pass
        elif raw.startswith("custom_"):
            custom_from_site = parse_custom_start_param(raw)
        elif raw.startswith("plan_"):
            pk = raw[5:]
            if pk:
                plan_from_mini = pk

    await get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or "",
        referrer_id=referrer_id,
    )

    if custom_from_site:
        months, devices = custom_from_site
        rub, usdt = await calc_custom_price(months, devices)
        plan_key = f"custom_{months}m_{devices}d"
        entries = await get_payment_method_entries()
        await message.answer(
            txt_constructor_result(months, devices, rub, usdt, promo_bonus_days=0),
            reply_markup=kb_payment_methods(
                plan_key, devices, method_entries=entries
            ),
            parse_mode="HTML",
        )
        return

    if plan_from_mini:
        plans_cat = await get_plans_catalog()
        if plan_from_mini in plans_cat:
            bd = 0
            entries = await get_payment_method_entries()
            await message.answer(
                txt_plan_detail(plan_from_mini, plans_cat, promo_bonus_days=bd),
                reply_markup=kb_payment_methods(
                    plan_from_mini, method_entries=entries
                ),
                parse_mode="HTML",
            )
            return
        await message.answer(
            "Тариф из ссылки больше не доступен. Выбери актуальный в меню ниже.",
            reply_markup=kb_main(),
        )
        return

    welcome_text = txt_welcome(message.from_user.first_name, ref_from_link=ref_bonus)
    banner = welcome_banner_path()
    # Подпись к фото в Telegram — не длиннее 1024 символов
    _CAPTION_MAX = 1024
    if banner is not None:
        cap = welcome_text if len(welcome_text) <= _CAPTION_MAX else None
        try:
            if cap is not None:
                await message.answer_photo(
                    FSInputFile(banner),
                    caption=cap,
                    reply_markup=kb_main(),
                    parse_mode="HTML",
                )
            else:
                await message.answer_photo(FSInputFile(banner))
                await message.answer(
                    welcome_text,
                    reply_markup=kb_main(),
                    parse_mode="HTML",
                )
        except TelegramBadRequest as e:
            err = str(e).lower()
            log.warning("welcome photo: %s", e)
            if "caption" in err or "too long" in err:
                await message.answer_photo(FSInputFile(banner))
                await message.answer(
                    welcome_text,
                    reply_markup=kb_main(),
                    parse_mode="HTML",
                )
            else:
                await message.answer(
                    welcome_text,
                    reply_markup=kb_main(),
                    parse_mode="HTML",
                )
    else:
        await message.answer(
            welcome_text,
            reply_markup=kb_main(),
            parse_mode="HTML",
        )


# ══════════════════════════════════════════════════════════════
#  НАВИГАЦИЯ
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "main")
async def cb_main(cb: CallbackQuery):
    await cq_edit_message(
        cb,
        txt_welcome(cb.from_user.first_name),
        reply_markup=kb_main(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "buy")
async def cb_buy(cb: CallbackQuery):
    bd = 0
    plans = await get_plans_catalog()
    await cq_edit_message(
        cb,
        txt_plans(plans, promo_bonus_days=bd),
        reply_markup=kb_plans(plans),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("plan:"))
async def cb_plan(cb: CallbackQuery):
    key = cb.data.split(":")[1]
    plans = await get_plans_catalog()
    if key not in plans:
        await cb.answer("Тариф недоступен.", show_alert=True)
        return
    bd = 0
    entries = await get_payment_method_entries()
    await cq_edit_message(
        cb,
        txt_plan_detail(key, plans, promo_bonus_days=bd),
        reply_markup=kb_payment_methods(key, method_entries=entries),
        parse_mode="HTML",
    )


# ── Конструктор ─────────────────────────────────────────────

@router.callback_query(F.data == "constructor")
async def cb_constructor(cb: CallbackQuery):
    await cq_edit_message(
        cb,
        txt_constructor_period(),
        reply_markup=kb_constructor_period(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cp:"))
async def cb_constructor_period(cb: CallbackQuery):
    months = int(cb.data.split(":")[1])
    await cq_edit_message(
        cb,
        txt_constructor_devices(months),
        reply_markup=kb_constructor_devices(months),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cd:"))
async def cb_constructor_devices(cb: CallbackQuery):
    _, months_s, devices_s = cb.data.split(":")
    months, devices = int(months_s), int(devices_s)
    devices = max(1, min(10, devices))
    rub, usdt = await calc_custom_price(months, devices)
    plan_key = f"custom_{months}m_{devices}d"
    bd = 0
    entries = await get_payment_method_entries()
    await cq_edit_message(
        cb,
        txt_constructor_result(months, devices, rub, usdt, promo_bonus_days=bd),
        reply_markup=kb_payment_methods(plan_key, devices, method_entries=entries),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════
#  ОПЛАТА
# ══════════════════════════════════════════════════════════════

@router.callback_query(
    F.data.startswith("pay:"),
    flags={"callback_answer": {"disabled": True}},
)
async def cb_pay(cb: CallbackQuery):
    parts = cb.data.split(":")
    # pay:<method>:<plan_key>[:<devices>]
    method   = parts[1]
    plan_key = parts[2]
    devices_override = int(parts[3]) if len(parts) > 3 else 0

    # Определяем параметры тарифа
    if plan_key.startswith("custom_"):
        # конструктор: custom_6m_3d
        segs    = plan_key.split("_")
        months  = int(segs[1].replace("m", ""))
        devices = max(1, min(10, int(segs[2].replace("d", ""))))
        if months not in (1, 6, 12):
            await cb.answer("Некорректный срок тарифа.", show_alert=True)
            return
        rub, usdt_amount = await calc_custom_price(months, devices)
    else:
        plans_cat = await get_plans_catalog()
        if plan_key not in plans_cat:
            await cb.answer("Тариф недоступен.", show_alert=True)
            return
        plan = plans_cat[plan_key]
        months  = plan["months"]
        devices = plan["devices"]
        rub     = plan["price_rub"]
        usdt_amount = plan["price_usdt"]

    devices = max(1, min(10, int(devices)))

    if method == "card_ru":
        await cb.answer(
            "Оплата картой через Freekassa отключена. Выбери другой способ.",
            show_alert=True,
        )
        return

    ton_amount = await rub_to_ton(rub)

    async with AsyncSessionLocal() as s:
        payment = Payment(
            user_tg_id  = cb.from_user.id,
            plan_key    = plan_key,
            devices     = devices,
            method      = method,
            amount_rub  = rub,
            amount_crypto = 0.0,
            currency    = "USDT" if method == "usdt_trc20" else ("TON" if method == "ton" else "RUB"),
            status      = "pending",
        )
        s.add(payment)
        await s.commit()
        await s.refresh(payment)
        payment_id = payment.id

        if method == "usdt_trc20":
            crypto_amt = unique_usdt_amount(usdt_amount, payment_id)
        elif method == "ton":
            crypto_amt = unique_ton_amount(ton_amount, payment_id)
        else:
            crypto_amt = 0.0
        if method in ("usdt_trc20", "ton"):
            await s.execute(
                update(Payment)
                .where(Payment.id == payment_id)
                .values(amount_crypto=crypto_amt)
            )
            await s.commit()

    # Отправляем инструкцию по оплате
    if method == "usdt_trc20":
        async with AsyncSessionLocal() as s:
            p = await s.scalar(select(Payment).where(Payment.id == payment_id))
            show_usdt = p.amount_crypto if p else unique_usdt_amount(usdt_amount, payment_id)
        ok = await cq_edit_message(
            cb,
            txt_pay_usdt(show_usdt, settings.USDT_TRC20_WALLET, str(payment_id)),
            reply_markup=kb_crypto_confirm(payment_id, method),
            parse_mode="HTML",
        )
        if ok:
            await cb.answer()
    elif method == "ton":
        async with AsyncSessionLocal() as s:
            p = await s.scalar(select(Payment).where(Payment.id == payment_id))
            show_ton = p.amount_crypto if p else unique_ton_amount(ton_amount, payment_id)
        ok = await cq_edit_message(
            cb,
            txt_pay_ton(show_ton, settings.TON_WALLET),
            reply_markup=kb_crypto_confirm(payment_id, method),
            parse_mode="HTML",
        )
        if ok:
            await cb.answer()
    elif method == "tbank":
        if not tbank_configured():
            await cb.answer("Оплата через Т-Банк не настроена.", show_alert=True)
            return
        from services import tbank as tbank_svc

        order_id = tbank_svc.order_id_for_payment(payment_id)
        test_mode = tbank_effective_test_mode()
        verify_ssl = tbank_effective_verify_ssl()
        base = tbank_svc.acquiring_base_url(
            test_mode=test_mode,
            override=(settings.TBANK_API_BASE or None),
        )
        pub = payment_public_base_url()
        notification_url = f"{pub}/payment/tbank" if pub else None
        success_url = f"{pub}/payment/success" if pub else None
        fail_url = f"{pub}/payment/fail" if pub else None
        kop = tbank_svc.rub_to_kopecks(rub)
        desc = f"NINAVPN {plan_key}"[:140]
        terminal = (settings.TBANK_TERMINAL_KEY or "").strip()
        password = (settings.TBANK_PASSWORD or "").strip()
        resp = await tbank_svc.init_payment(
            terminal,
            password,
            order_id=order_id,
            amount_kopecks=kop,
            description=desc,
            base_url=base,
            notification_url=notification_url,
            success_url=success_url,
            fail_url=fail_url,
            verify_ssl=verify_ssl,
        )
        if not resp.get("Success"):
            log.error(
                "T-Bank Init failed: %s (test_mode=%s verify_ssl=%s base=%s)",
                resp,
                test_mode,
                verify_ssl,
                base,
            )
            await cb.answer(
                "Не удалось создать оплату. Попробуй позже или другой способ.",
                show_alert=True,
            )
            return
        pay_url = (resp.get("PaymentURL") or "").strip()
        if not pay_url:
            log.error("T-Bank Init: нет PaymentURL %s", resp)
            await cb.answer("Ошибка ссылки оплаты.", show_alert=True)
            return
        ext_id = str(resp.get("PaymentId") or "")[:128]
        async with AsyncSessionLocal() as s:
            await s.execute(
                update(Payment).where(Payment.id == payment_id).values(tx_hash=ext_id or None)
            )
            await s.commit()
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="💳 Перейти к оплате", url=pay_url))
        b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy"))
        ok = await cq_edit_message(
            cb,
            txt_pay_tbank(rub, payment_id, webhook_ok=bool(pub)),
            reply_markup=b.as_markup(),
            parse_mode="HTML",
        )
        if ok and cb.message:
            try:
                qr_b64 = get_vpn_panel().make_qr_base64(pay_url)
                await cb.message.answer_photo(
                    BufferedInputFile(base64.b64decode(qr_b64), "tbank_pay.png"),
                    caption="📱 QR на страницу оплаты (карта / СБП)",
                )
            except Exception as e:
                log.warning("tbank QR: %s", e)
        if ok:
            await cb.answer()
    elif method == "sber_pbpn":
        if not sber_pbpn_configured():
            await cb.answer("Перевод по ссылке не настроен.", show_alert=True)
            return
        url = sber_pay_url(rub)
        ok = await cq_edit_message(
            cb,
            txt_pay_sber(url, rub, payment_id),
            reply_markup=kb_sber_pay(url, payment_id),
            parse_mode="HTML",
        )
        if ok:
            await cb.answer()


# ── Перевод по ссылке (sber_pbpn): уведомление админам ───────

@router.callback_query(F.data.startswith("sber_notify:"))
async def cb_sber_notify(cb: CallbackQuery, bot: Bot):
    payment_id = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as s:
        payment = await s.scalar(select(Payment).where(Payment.id == payment_id))
        db_user = await s.scalar(select(User).where(User.tg_id == cb.from_user.id))
    if not payment or payment.user_tg_id != cb.from_user.id:
        await cb.answer("Заказ не найден.", show_alert=True)
        return
    if payment.method != "sber_pbpn":
        await cb.answer("Неверный тип платежа.", show_alert=True)
        return
    if payment.status != "pending":
        await cb.answer("Этот заказ уже обработан.", show_alert=True)
        return
    if payment.admin_notify_sent:
        await cb.answer("Админам уже отправлено. Ожидай подтверждения.", show_alert=True)
        return

    async with AsyncSessionLocal() as s:
        res = await s.execute(
            update(Payment)
            .where(
                Payment.id == payment_id,
                Payment.admin_notify_sent == False,
                Payment.status == "pending",
            )
            .values(admin_notify_sent=True)
        )
        await s.commit()
        if res.rowcount != 1:
            async with AsyncSessionLocal() as s2:
                p_retry = await s2.scalar(select(Payment).where(Payment.id == payment_id))
            if p_retry and p_retry.admin_notify_sent:
                await cb.answer("Админам уже отправлено. Ожидай подтверждения.", show_alert=True)
            else:
                await cb.answer("Не удалось зафиксировать. Попробуй ещё раз.", show_alert=True)
            return

    uname = f"@{db_user.username}" if db_user and db_user.username else "без username"
    full = (db_user.full_name or "—") if db_user else "—"
    amt = float(payment.amount_rub or 0)
    admin_text = (
        f"🏦 <b>Т-Банк (перевод): запрос на подтверждение</b>\n\n"
        f"Платёж <code>#{payment_id}</code>\n"
        f"Пользователь: {html_escape(full)} ({html_escape(uname)}) "
        f"id <code>{cb.from_user.id}</code>\n"
        f"Сумма: <b>{amt:.2f} ₽</b>\n"
        f"Тариф: <code>{html_escape(payment.plan_key)}</code>, "
        f"устройств: {payment.devices}\n\n"
        f"Проверь поступление перевода, затем подтверди или отклони."
    )
    for aid in admin_id_set():
        try:
            await bot.send_message(
                aid,
                admin_text,
                parse_mode="HTML",
                reply_markup=kb_admin_confirm_payment(payment_id),
            )
        except Exception as e:
            log.warning("sber_notify: не удалось отправить админу %s: %s", aid, e)
    await cb.answer("Отправлено администратору. Ожидай активации.")


# ── Админ: подтверждение перевода (sber_pbpn) ─────────────────

@router.callback_query(F.data.startswith("adm_ok:"))
async def cb_adm_ok(cb: CallbackQuery, bot: Bot):
    if cb.from_user.id not in admin_id_set():
        await cb.answer("Нет доступа.", show_alert=True)
        return
    payment_id = int(cb.data.split(":")[1])

    async with AsyncSessionLocal() as s:
        payment = await s.scalar(select(Payment).where(Payment.id == payment_id))
        if not payment:
            await cb.answer("Платёж не найден.", show_alert=True)
            return
        if payment.status == "confirmed":
            await cb.answer("Уже подтверждён.", show_alert=True)
            return
        if payment.method != "sber_pbpn":
            await cb.answer("Не перевод с ручным подтверждением.", show_alert=True)
            return
        if payment.status != "pending":
            await cb.answer(f"Статус: {payment.status}", show_alert=True)
            return

        plan_key = payment.plan_key
        months = await _months_from_plan_key(plan_key)
        devices = payment.devices
        amount_rub_pay = payment.amount_rub or 0
        tg_id = payment.user_tg_id

        res = await s.execute(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == "pending")
            .values(status="processing")
        )
        await s.commit()
        if res.rowcount != 1:
            p2 = await s.scalar(select(Payment).where(Payment.id == payment_id))
            if p2 and p2.status == "confirmed":
                await cb.answer("Уже подтверждён.", show_alert=True)
                return
            log.warning("adm_ok: race payment_id=%s", payment_id)
            await cb.answer("Не удалось захватить платёж.", show_alert=True)
            return

    await issue_config(bot, tg_id, plan_key, devices, months, amount_rub_pay, payment_id)

    async with AsyncSessionLocal() as s:
        p3 = await s.scalar(select(Payment).where(Payment.id == payment_id))
        if not p3 or p3.status != "confirmed":
            await _revert_payment_processing(payment_id)
            log.error("adm_ok: выдача не завершилась payment_id=%s", payment_id)
            await cb.answer("Ошибка выдачи конфига. Платёж возвращён в ожидание.", show_alert=True)
            return

    await cb.answer("Подписка выдана.")
    if cb.message:
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
            await cb.message.reply("✅ Платёж подтверждён, пользователю отправлен конфиг.")
        except TelegramBadRequest:
            pass


@router.callback_query(F.data.startswith("adm_no:"))
async def cb_adm_no(cb: CallbackQuery, bot: Bot):
    if cb.from_user.id not in admin_id_set():
        await cb.answer("Нет доступа.", show_alert=True)
        return
    payment_id = int(cb.data.split(":")[1])
    user_tg: Optional[int] = None
    async with AsyncSessionLocal() as s:
        payment = await s.scalar(select(Payment).where(Payment.id == payment_id))
        if not payment:
            await cb.answer("Платёж не найден.", show_alert=True)
            return
        if payment.method != "sber_pbpn":
            await cb.answer("Не перевод с ручным подтверждением.", show_alert=True)
            return
        if payment.status != "pending":
            await cb.answer(f"Статус уже: {payment.status}", show_alert=True)
            return
        user_tg = int(payment.user_tg_id)
        await s.execute(
            update(Payment).where(Payment.id == payment_id).values(status="failed")
        )
        await s.commit()
    if user_tg:
        try:
            await bot.send_message(
                user_tg,
                "❌ Оплата по заказу не подтверждена администратором. "
                "Если перевод был — напиши в поддержку с чеком.",
            )
        except Exception as e:
            log.warning("adm_no: не удалось уведомить user %s: %s", user_tg, e)
    await cb.answer("Отклонено.")
    if cb.message:
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
            await cb.message.reply("❌ Платёж отклонён.")
        except TelegramBadRequest:
            pass


# ── Проверка крипто-оплаты ──────────────────────────────────

@router.callback_query(
    F.data.startswith("check:"),
    flags={"callback_answer": {"disabled": True}},
)
async def cb_check(cb: CallbackQuery, bot: Bot):
    _, payment_id_s, method = cb.data.split(":")
    payment_id = int(payment_id_s)

    await cb.answer()
    await cq_edit_message(cb, txt_payment_checking(), parse_mode="HTML")

    async with AsyncSessionLocal() as s:
        payment = await s.scalar(select(Payment).where(Payment.id == payment_id))
        if not payment or payment.status == "confirmed":
            await cq_edit_message(cb, "✅ Уже обработано!", parse_mode="HTML")
            return

    # Проверяем в блокчейне (сумма в БД уже уникальна для этого payment_id)
    tx = None
    if method == "usdt_trc20":
        tx = await check_usdt_payment(
            settings.USDT_TRC20_WALLET, float(payment.amount_crypto or 0)
        )
    elif method == "ton":
        tx = await check_ton_payment(
            settings.TON_WALLET, float(payment.amount_crypto or 0)
        )

    if tx:
        async with AsyncSessionLocal() as s:
            dup = await s.scalar(
                select(Payment).where(
                    Payment.tx_hash == tx["tx_hash"],
                    Payment.status == "confirmed",
                    Payment.id != payment_id,
                )
            )
            if dup:
                await cq_edit_message(
                    cb,
                    "❌ Эта транзакция уже привязана к другому заказу. Напишите в поддержку.",
                    parse_mode="HTML",
                )
                return
            res = await s.execute(
                update(Payment)
                .where(Payment.id == payment_id, Payment.status == "pending")
                .values(status="processing", tx_hash=tx["tx_hash"])
            )
            await s.commit()
            if res.rowcount != 1:
                await cq_edit_message(cb, "✅ Уже обработано!", parse_mode="HTML")
                return

        plan_key = payment.plan_key
        months = await _months_from_plan_key(plan_key)

        await issue_config(
            bot, cb.from_user.id, plan_key,
            payment.devices, months, payment.amount_rub, payment_id,
        )

        async with AsyncSessionLocal() as s:
            p3 = await s.scalar(select(Payment).where(Payment.id == payment_id))
            if not p3 or p3.status != "confirmed":
                await _revert_payment_processing(payment_id)
                async with AsyncSessionLocal() as s2:
                    await s2.execute(
                        update(Payment)
                        .where(Payment.id == payment_id)
                        .values(tx_hash=None)
                    )
                    await s2.commit()
                await cq_edit_message(
                    cb,
                    "❌ Не удалось выдать конфиг. Напишите в поддержку.",
                    parse_mode="HTML",
                )
                return
        try:
            await cq_edit_message(
                cb,
                "✅ <b>Оплата подтверждена!</b> Конфиг и QR отправлены выше.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        # Не найдено — даём повторить
        await cq_edit_message(
            cb,
            txt_payment_not_found(),
            reply_markup=kb_crypto_confirm(payment_id, method),
            parse_mode="HTML",
        )


# ══════════════════════════════════════════════════════════════
#  МОИ ПОДПИСКИ
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "my_subs")
async def cb_my_subs(cb: CallbackQuery):
    now = datetime.utcnow()
    live_un = await sync_username_from_telegram(cb.bot, cb.from_user.id)
    tg_disp = live_un or (cb.from_user.username or "").strip().lstrip("@") or None
    async with AsyncSessionLocal() as s:
        subs = (await s.execute(
            select(Subscription)
            .where(Subscription.user_tg_id == cb.from_user.id)
            .order_by(Subscription.started_at.desc())
        )).scalars().all()

    if not subs:
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="🛒 Купить", callback_data="buy"))
        b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main"))
        await cq_edit_message(cb, txt_my_subs_empty(), reply_markup=b.as_markup(), parse_mode="HTML")
        return

    def _is_live(sub: Subscription) -> bool:
        return bool(
            sub.is_active and sub.expires_at and sub.expires_at > now
        )

    active = [x for x in subs if _is_live(x)]
    primary = max(active, key=lambda x: x.expires_at) if active else None

    if primary:
        left = (primary.expires_at - now).days if primary.expires_at else 0
        text = (
            "📋 <b>Твоя подписка</b>\n\n"
            f"{txt_sub_info(primary, telegram_username=tg_disp)}\n\n"
            "Ниже — действия и история покупок."
        )
        await cq_edit_message(
            cb,
            text,
            reply_markup=kb_sub_actions(primary.id),
            parse_mode="HTML",
        )
        return

    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🛒 Купить / продлить", callback_data="buy"))
    for sub in subs[:6]:
        left = (sub.expires_at - now).days if sub.expires_at else 0
        icon = "🟢" if sub.is_active and left > 0 else "🔴"
        b.row(InlineKeyboardButton(
            text=f"{icon} {sub.plan_key} · до {sub.expires_at.strftime('%d.%m') if sub.expires_at else '—'}",
            callback_data=f"sub:{sub.id}",
        ))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main"))
    await cq_edit_message(
        cb,
        "📋 <b>Подписок сейчас нет.</b>\n\nНиже — последние записи:",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(
    F.data == "my_subs_hist",
    flags={"callback_answer": {"disabled": True}},
)
async def cb_my_subs_hist(cb: CallbackQuery):
    async with AsyncSessionLocal() as s:
        subs = (await s.execute(
            select(Subscription)
            .where(Subscription.user_tg_id == cb.from_user.id)
            .order_by(Subscription.started_at.desc())
            .limit(12)
        )).scalars().all()
    if not subs:
        await cb.answer("История пуста", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    now = datetime.utcnow()
    for sub in subs:
        left = (sub.expires_at - now).days if sub.expires_at else 0
        live = sub.is_active and sub.expires_at and sub.expires_at > now
        icon = "🟢" if live else "⚪"
        b.row(InlineKeyboardButton(
            text=f"{icon} #{sub.id} {sub.plan_key} · {sub.expires_at.strftime('%d.%m.%y') if sub.expires_at else '—'}",
            callback_data=f"sub:{sub.id}",
        ))
    b.row(InlineKeyboardButton(text="◀️ К подписке", callback_data="my_subs"))
    await cq_edit_message(
        cb,
        "📜 <b>История покупок</b>\n\nВыбери запись для деталей:",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(
    F.data.startswith("sub:"),
    flags={"callback_answer": {"disabled": True}},
)
async def cb_sub_detail(cb: CallbackQuery):
    sub_id = int(cb.data.split(":")[1])
    live_un = await sync_username_from_telegram(cb.bot, cb.from_user.id)
    tg_disp = live_un or (cb.from_user.username or "").strip().lstrip("@") or None
    async with AsyncSessionLocal() as s:
        sub = await s.scalar(select(Subscription).where(Subscription.id == sub_id))
    if not sub or sub.user_tg_id != cb.from_user.id:
        await cb.answer("Подписка не найдена", show_alert=True)
        return
    await cq_edit_message(
        cb,
        f"📋 <b>Подписка #{sub.id}</b>\n\n{txt_sub_info(sub, telegram_username=tg_disp)}",
        reply_markup=kb_sub_actions(sub.id),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(
    F.data.startswith("renew:"),
    flags={"callback_answer": {"disabled": True}},
)
async def cb_renew(cb: CallbackQuery):
    """Продление: тот же plan_key и устройства, дальше — выбор способа оплаты."""
    sub_id = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as s:
        sub = await s.scalar(select(Subscription).where(Subscription.id == sub_id))
    if not sub or sub.user_tg_id != cb.from_user.id:
        await cb.answer("Подписка не найдена", show_alert=True)
        return

    bd = 0
    pk = sub.plan_key
    if pk.startswith("custom_"):
        try:
            segs = pk.split("_")
            months = int(segs[1].replace("m", ""))
            dev_from_key = int(segs[2].replace("d", ""))
        except (IndexError, ValueError):
            await cb.answer("Не удалось разобрать тариф. Оформи покупку из каталога.", show_alert=True)
            return
        if months not in (1, 6, 12):
            await cb.answer("Тариф устарел. Оформи покупку из каталога.", show_alert=True)
            return
        devices = max(1, min(10, int(sub.devices or dev_from_key)))
        rub, usdt = await calc_custom_price(months, devices)
        text = "➕ <b>Продление</b>\n\n" + txt_constructor_result(
            months, devices, rub, usdt, promo_bonus_days=bd,
        )
        entries = await get_payment_method_entries()
        await cq_edit_message(
            cb,
            text,
            reply_markup=kb_payment_methods(
                pk, devices, back_callback=f"sub:{sub_id}", method_entries=entries,
            ),
            parse_mode="HTML",
        )
        await cb.answer()
        return

    plans = await get_plans_catalog()
    if pk not in plans:
        await cb.answer("Этот тариф недоступен. Выбери новый в «Купить подписку».", show_alert=True)
        return

    header = "➕ <b>Продление подписки</b>\n\n"
    entries = await get_payment_method_entries()
    await cq_edit_message(
        cb,
        header + txt_plan_detail(pk, plans, promo_bonus_days=bd),
        reply_markup=kb_payment_methods(
            pk, 0, back_callback=f"sub:{sub_id}", method_entries=entries,
        ),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(
    F.data.startswith("getconf:"),
    flags={"callback_answer": {"disabled": True}},
)
async def cb_getconf(cb: CallbackQuery, bot: Bot):
    await cb.answer()
    sub_id = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as s:
        sub = await s.scalar(select(Subscription).where(Subscription.id == sub_id))
    if not sub or sub.user_tg_id != cb.from_user.id:
        await cq_edit_message(cb, "❌ Подписка не найдена.", parse_mode="HTML")
        return
    panel = get_vpn_panel()
    dev = max(1, min(10, int(sub.devices or 1)))
    if not await panel.sync_device_limit(sub.user_tg_id, dev):
        log.warning(
            "sync_device_limit перед выдачей конфига: tg_id=%s devices=%s",
            sub.user_tg_id,
            dev,
        )
    refresh = getattr(panel, "refresh_share_links_for_tg", None)
    main_link = (sub.config_link or "").strip()
    extra_link = (sub.config_link_extra or "").strip() or None
    urls_for_qr: list[str] = []
    if refresh:
        fresh, _ = await refresh(sub.user_tg_id)
        if fresh:
            main_link = fresh[0]
            extra_link = fresh[1] if len(fresh) > 1 else None
            urls_for_qr = list(fresh)
    if not main_link:
        await cq_edit_message(
            cb,
            "❌ Конфиг недоступен. Напишите в поддержку.",
            parse_mode="HTML",
        )
        return
    if not urls_for_qr:
        urls_for_qr = [main_link] + ([extra_link] if extra_link else [])
    expires_str = sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else "—"
    await send_config_ready_bundle(
        bot,
        cb.from_user.id,
        main_link,
        expires_str,
        sub.devices,
        extra_link=extra_link,
        partial_nodes=False,
        reply_markup=None,
    )
    urls = urls_for_qr
    for i, url in enumerate(urls):
        try:
            qr_b64 = get_vpn_panel().make_qr_base64(url)
            v = url.startswith("vless://")
            cap = (
                ("📱 QR — VLESS (основной)" if v else "📱 QR — основной")
                if i == 0
                else ("📱 QR — VLESS (запасной)" if v else "📱 QR — запасной")
            )
            await bot.send_photo(
                cb.from_user.id,
                BufferedInputFile(base64.b64decode(qr_b64), f"config_{i}.png"),
                caption=cap,
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("stat:"))
async def cb_stat(cb: CallbackQuery):
    sub_id = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as s:
        sub = await s.scalar(select(Subscription).where(Subscription.id == sub_id))
    if not sub:
        await cb.answer("Не найдено", show_alert=True)
        return
    usage = await get_vpn_panel().get_usage(sub.user_tg_id)
    per = usage.get("per_node") or ""
    if len(per) > 120:
        per = per[:117] + "..."
    extra = f"\n{per}" if per else ""
    msg = (
        f"📊 Всего: {usage.get('used_gb', 0)} ГБ\n"
        f"Статус: {usage.get('status', '—')}{extra}"
    )
    if len(msg) > 190:
        msg = msg[:187] + "..."
    await cb.answer(msg, show_alert=True)


# ══════════════════════════════════════════════════════════════
#  СЕРВЕРЫ / ПРОМОКОД / РЕФЕРАЛ / ПОДДЕРЖКА / HOWTO
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "servers")
async def cb_servers(cb: CallbackQuery):
    from services.server_status import get_servers_status_message

    text = await get_servers_status_message()
    await cq_edit_message(
        cb, text, reply_markup=kb_servers_back(), parse_mode="HTML"
    )


@router.callback_query(F.data == "support")
async def cb_support(cb: CallbackQuery):
    await cq_edit_message(
        cb,
        "💬 <b>Поддержка NINAVPN</b>\n\n"
        "Мы онлайн с 9:00 до 23:00. Отвечаем быстро 🚀\n\n"
        "<i>Сообщение можно отправить через бота — без открытия личного профиля.</i>",
        reply_markup=kb_support(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "support:chat")
async def cb_support_chat(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_message)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="support:cancel"))
    await cb.message.answer(
        "✍️ <b>Напиши сообщение для поддержки</b> в этот чат (текст или фото).\n\n"
        "Ответ придёт сюда же от бота.\n"
        "Отмена: кнопка ниже или команда /cancel",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "support:cancel")
async def cb_support_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer("Отменено")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass


@router.message(Command("cancel"), StateFilter(SupportStates.waiting_message))
async def cmd_cancel_support(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Ок, отменено. Снова: «Поддержка» в меню.")


@router.message(
    StateFilter(SupportStates.waiting_message),
    F.text & ~F.text.startswith("/"),
)
async def support_forward_text(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    un = message.from_user.username or "—"
    fn = message.from_user.full_name or "—"
    body = (message.text or "").strip()
    if not body:
        await message.answer("Пустое сообщение. Напиши текст или нажми «Отмена».")
        return
    header = (
        f"💬 <b>Сообщение в поддержку</b>\n"
        f"От: {html_escape(fn)} (@{html_escape(un)}) id <code>{uid}</code>\n\n"
        f"{html_escape(body)}"
    )
    for aid in admin_id_set():
        try:
            await bot.send_message(aid, header, parse_mode="HTML")
        except Exception as e:
            log.warning("support: не отправилось админу %s: %s", aid, e)
    await state.clear()
    try:
        await message.answer(
            "✅ Сообщение отправлено администратору. Ответ придёт в этот чат.",
            reply_markup=kb_main(),
        )
    except TelegramBadRequest:
        await message.answer("✅ Сообщение отправлено администратору.")


@router.message(StateFilter(SupportStates.waiting_message), F.photo)
async def support_forward_photo(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    for aid in admin_id_set():
        try:
            await bot.forward_message(aid, message.chat.id, message.message_id)
            await bot.send_message(
                aid,
                f"↑ <b>Поддержка</b>, user id <code>{uid}</code>",
                parse_mode="HTML",
            )
        except Exception as e:
            log.warning("support photo: админ %s: %s", aid, e)
    await state.clear()
    await message.answer(
        "✅ Фото отправлено. Ответ придёт в этот чат.",
        reply_markup=kb_main(),
    )


@router.message(StateFilter(SupportStates.waiting_message))
async def support_forward_other(message: Message, state: FSMContext, bot: Bot):
    """Стикеры, документы, голосовые — пересылаем как есть."""
    uid = message.from_user.id
    for aid in admin_id_set():
        try:
            await bot.forward_message(aid, message.chat.id, message.message_id)
            await bot.send_message(
                aid,
                f"↑ <b>Поддержка</b>, user id <code>{uid}</code>",
                parse_mode="HTML",
            )
        except Exception as e:
            log.warning("support media: админ %s: %s", aid, e)
    await state.clear()
    await message.answer(
        "✅ Отправлено. Ответ придёт в этот чат.",
        reply_markup=kb_main(),
    )


@router.callback_query(F.data == "howto")
async def cb_howto_menu(cb: CallbackQuery):
    await cq_edit_message(
        cb,
        "📱 <b>Инструкции по подключению</b>\n\nВыбери своё устройство:",
        reply_markup=kb_howto(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("howto:"))
async def cb_howto_platform(cb: CallbackQuery):
    platform = cb.data.split(":")[1]
    text = txt_howto(platform)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="howto"))
    await cq_edit_message(cb, text, reply_markup=b.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "referral")
async def cb_referral(cb: CallbackQuery):
    async with AsyncSessionLocal() as s:
        invited_reg = int(
            await s.scalar(
                select(func.count()).where(User.referrer_id == cb.from_user.id)
            )
            or 0
        )
        invited_paid = int(
            await s.scalar(
                select(func.count()).where(
                    User.referrer_id == cb.from_user.id,
                    User.ref_bonus_given.is_(True),
                )
            )
            or 0
        )
    rb = int(settings.REFERRAL_BONUS_DAYS or 30)
    earned = invited_paid * rb
    await cq_edit_message(
        cb,
        txt_referral(
            cb.from_user.id,
            invited_registered=invited_reg,
            invited_paid=invited_paid,
            earned_days=earned,
            referrer_bonus_days=rb,
            invitee_bonus_days=int(settings.REFERRAL_INVITEE_BONUS_DAYS or 0),
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Назад", callback_data="main")
        ]]),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "promo")
async def cb_promo(cb: CallbackQuery):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main"))
    await cq_edit_message(
        cb,
        "🎁 <b>Промокод</b>\n\nВведи промокод текстом в чат:",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )


@router.message(
    F.text & ~F.text.startswith("/"),
    ~StateFilter(SupportStates.waiting_message),
)
async def msg_promo_input(message: Message):
    code = message.text.strip().upper()
    bot = message.bot
    async with AsyncSessionLocal() as s:
        promo = await s.scalar(
            select(PromoCode).where(
                PromoCode.code == code,
                PromoCode.is_active == True,
            )
        )
        if not promo:
            await message.answer("❌ Промокод не найден или уже неактивен.")
            return
        if promo.used_count >= promo.max_uses:
            await message.answer(
                "❌ Промокод исчерпан (достигнут общий лимит активаций)."
            )
            return
        if promo.expires_at and promo.expires_at < datetime.utcnow():
            await message.answer("❌ Промокод истёк.")
            return
        user = await s.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            user = User(
                tg_id=message.from_user.id,
                username=message.from_user.username or "",
                full_name=message.from_user.full_name or "",
            )
            s.add(user)
            await s.flush()
        dup = await s.scalar(
            select(PromoRedemption).where(
                PromoRedemption.promo_id == promo.id,
                PromoRedemption.user_tg_id == message.from_user.id,
            )
        )
        if dup:
            await message.answer("❌ Ты уже использовал этот промокод.")
            return
        await s.commit()

    bd = int(promo.bonus_days or 0)
    if bd <= 0:
        await message.answer(
            "❌ Некорректный промокод. "
            "Нужен код с числом бесплатных дней (выдаёт админ: /promo_add CODE ДНИ).",
        )
        return

    try:
        await sync_username_from_telegram(bot, message.from_user.id)
    except Exception:
        log.debug("promo: sync_username_from_telegram", exc_info=True)
    live_un = (message.from_user.username or "").strip().lstrip("@")
    if live_un:
        async with AsyncSessionLocal() as s:
            u = await s.scalar(select(User).where(User.tg_id == message.from_user.id))
            if u and not (u.username or "").strip():
                u.username = live_un
                await s.commit()

    panel = get_vpn_panel()
    try:
        res = await panel.grant_free_days(message.from_user.id, bd, 1)
    except Exception:
        log.exception("promo grant_free_days")
        await message.answer(
            "❌ Не удалось выдать доступ VPN. Попробуй позже или напиши в поддержку.",
        )
        return

    if not res.get("ok"):
        log.warning(
            "promo grant_free_days ok=false tg_id=%s res_keys=%s links_n=%s sub_len=%s",
            message.from_user.id,
            list(res.keys()),
            len(res.get("links") or []),
            len(str(res.get("subscription_url") or "")),
        )
        await message.answer(
            "❌ Не удалось активировать промокод на стороне VPN. "
            "Попробуй позже или напиши в поддержку.",
        )
        return

    links = [x for x in (res.get("links") or []) if x]
    primary = (res.get("subscription_url") or "").strip() or (links[0] if links else "")
    if not primary:
        await message.answer(
            "❌ Доступ выдан частично, но ссылка не получена. Напиши в поддержку.",
        )
        return

    exp = res.get("expires")
    if exp is None:
        exp = datetime.utcnow() + timedelta(days=bd)

    await panel.sync_device_limit(message.from_user.id, 1)

    async with AsyncSessionLocal() as s:
        try:
            s.add(
                PromoRedemption(
                    promo_id=promo.id,
                    user_tg_id=message.from_user.id,
                )
            )
            pr = await s.get(PromoCode, promo.id)
            if pr:
                pr.used_count = (pr.used_count or 0) + 1
            await _upsert_subscription_after_promo(
                s,
                message.from_user.id,
                links,
                primary,
                exp,
                1,
            )
            await s.commit()
        except IntegrityError:
            await s.rollback()
            await message.answer("❌ Этот промокод ты уже использовал.")
            return

    esc = html_escape(code)
    expires_str = exp.strftime("%d.%m.%Y")
    await message.answer(
        f"✅ Промокод <b>{esc}</b> активирован!\n"
        f"Тебе начислено <b>{bd}</b> дн. бесплатного доступа к VPN.\n"
        f"До: <b>{expires_str}</b>.\n\n"
        "Ниже — ссылка и QR.",
        parse_mode="HTML",
    )
    await send_config_ready_bundle(
        bot,
        message.from_user.id,
        primary,
        expires_str,
        1,
        extra_link=links[1] if len(links) > 1 else None,
        partial_nodes=False,
        reply_markup=kb_after_config(),
    )
    panel_q = get_vpn_panel()
    for i, url in enumerate(links):
        if not url:
            continue
        try:
            qr_b64 = panel_q.make_qr_base64(url)
            qr_bytes = base64.b64decode(qr_b64)
            v = url.startswith("vless://")
            cap = (
                ("📱 QR — VLESS (основной)" if v else "📱 QR — основной")
                if i == 0
                else ("📱 QR — VLESS (запасной)" if v else "📱 QR — запасной")
            )
            await bot.send_photo(
                message.from_user.id,
                BufferedInputFile(qr_bytes, filename=f"ninavpn_promo_{i}.png"),
                caption=cap,
            )
        except Exception as e:
            log.warning("promo QR: %s", e)


# ══════════════════════════════════════════════════════════════
#  ADMIN КОМАНДЫ
# ══════════════════════════════════════════════════════════════

def admin_only(func):
    """Пропускает в хэндлер только аргументы из сигнатуры (aiogram шлёт ещё dispatcher и т.д.)."""
    sig = inspect.signature(func)
    param_names = set(sig.parameters)

    @functools.wraps(func)
    async def wrapper(message: Message, **kwargs):
        user_id = getattr(getattr(message, "from_user", None), "id", None)
        allowed = admin_id_set()
        if user_id not in allowed:
            log.warning("Admin access denied: from_user.id=%s", user_id)
            uid = user_id if user_id is not None else "?"
            await message.answer(
                "⛔ <b>Доступ только для администратора.</b>\n\n"
                f"Ваш Telegram ID: <code>{uid}</code>\n"
                "На сервере в <code>.env</code> должны совпадать "
                "<code>ADMIN_ID</code> (или список <code>ADMIN_IDS</code> через запятую) "
                "с этим числом. Узнать ID можно у @userinfobot.\n"
                "Пишите команду в <b>личке</b> с ботом.",
                parse_mode="HTML",
            )
            return None
        call_kw = {k: v for k, v in kwargs.items() if k in param_names}
        return await func(message, **call_kw)

    return wrapper


@router.message(Command("admin"))
@admin_only
async def cmd_admin(message: Message):
    async with AsyncSessionLocal() as s:
        total_users = len((await s.execute(select(User))).scalars().all())
        active_subs = len((await s.execute(
            select(Subscription).where(
                Subscription.is_active == True,
                Subscription.expires_at > datetime.utcnow(),
            )
        )).scalars().all())
        pending_rows = (
            await s.execute(select(Payment).where(Payment.status == "pending"))
        ).scalars().all()
        pending_need_admin = sum(
            1
            for p in pending_rows
            if p.method == "sber_pbpn" and (p.admin_notify_sent or False)
        )
        pending_unfinished = len(pending_rows)

    await message.answer(
        f"🔐 <b>Админ-панель NINAVPN</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"✅ Активных подписок: <b>{active_subs}</b>\n"
        f"🔔 К подтверждению <b>перевода</b> (пользователь нажал «сообщить админу»): "
        f"<b>{pending_need_admin}</b>\n"
        f"🛒 Незавершённых заказов всего (крипта / карта / ожидание оплаты и т.д.): "
        f"<b>{pending_unfinished}</b>\n\n"
        f"Команды:\n"
        f"/stats — полная статистика\n"
        f"/promo_add CODE ДНИ — промокод: бесплатные дни VPN (1 раз на пользователя)\n"
        f"/plan_list — тарифы в базе (и подсказка по каталогу)\n"
        f"/plan_add JSON — добавить/обновить тариф в базе\n"
        f"/plan_import_builtin — загрузить встроенные тарифы в БД для правки\n"
        f"/plan_del KEY — удалить тариф из БД\n"
        f"/broadcast — рассылка всем пользователям",
        parse_mode="HTML",
    )


@router.message(Command("stats"))
@admin_only
async def cmd_stats(message: Message):
    async with AsyncSessionLocal() as s:
        users = (await s.execute(select(User))).scalars().all()
        payments = (await s.execute(
            select(Payment).where(Payment.status == "confirmed")
        )).scalars().all()
        total_revenue = sum(p.amount_rub or 0 for p in payments)
        month_ago = datetime.utcnow() - timedelta(days=30)
        month_rev = sum(p.amount_rub or 0 for p in payments if p.confirmed_at and p.confirmed_at > month_ago)

    await message.answer(
        f"📊 <b>Статистика NINAVPN</b>\n\n"
        f"👥 Пользователей: <b>{len(users)}</b>\n"
        f"💰 Выручка всего: <b>{total_revenue:.0f} ₽</b>\n"
        f"📅 За последние 30 дн.: <b>{month_rev:.0f} ₽</b>\n"
        f"🧾 Успешных платежей: <b>{len(payments)}</b>",
        parse_mode="HTML",
    )


@router.message(Command("promo_add"))
@admin_only
async def cmd_promo_add(message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "Формат: /promo_add CODE ДНИ\n"
            "ДНИ — целые <b>календарные дни</b> доступа (не часы). "
            "Пример: один день — <code>/promo_add FREE1 1</code>; "
            "24 дня — <code>/promo_add FREE24 24</code>.\n"
            "Один раз на пользователя; общий лимит — max_uses в БД.",
            parse_mode="HTML",
        )
        return
    code = parts[1].upper()
    try:
        days = int(parts[2])
    except ValueError:
        await message.answer("Число дней должно быть целым.")
        return
    if days <= 0 or days > 3650:
        await message.answer("Дни: от 1 до 3650.")
        return
    async with AsyncSessionLocal() as s:
        exists = await s.scalar(select(PromoCode).where(PromoCode.code == code))
        if exists:
            await message.answer(f"❌ Код <b>{code}</b> уже есть. Другой CODE или правь в БД.", parse_mode="HTML")
            return
        promo = PromoCode(
            code=code,
            discount_pct=0,
            bonus_days=days,
            max_uses=100_000,
            is_active=True,
        )
        s.add(promo)
        await s.commit()
    await message.answer(
        f"✅ Промокод <b>{code}</b>: <b>{days}</b> бесплатных дн. VPN при активации "
        f"(один раз на пользователя).",
        parse_mode="HTML",
    )


def _parse_plan_json(raw: str) -> dict:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Ожидается JSON-объект")
    return data


@router.message(Command("plan_list"))
@admin_only
async def cmd_plan_list(message: Message):
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(PlanTariff).order_by(
                    PlanTariff.sort_order.asc(), PlanTariff.plan_key.asc()
                )
            )
        ).scalars().all()
    if not rows:
        await message.answer(
            "📋 В базе нет тарифов — бот показывает <b>встроенный</b> каталог из кода.\n"
            "Чтобы править цены и ссылки: <code>/plan_import_builtin</code> "
            "или <code>/plan_add</code> с JSON.",
            parse_mode="HTML",
        )
        return
    lines = [
        "📋 <b>Тарифы в БД</b> (пока есть хотя бы один активный — каталог только отсюда):\n",
    ]
    for r in rows:
        act = "🟢" if r.is_active else "⏸"
        lines.append(
            f"{act} <code>{r.plan_key}</code> · {r.emoji or ''} {r.name} · "
            f"{r.price_rub:g} ₽"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("plan_import_builtin"))
@admin_only
async def cmd_plan_import_builtin(message: Message):
    n = 0
    async with AsyncSessionLocal() as s:
        for i, (key, p) in enumerate(PLANS.items()):
            row = await s.scalar(select(PlanTariff).where(PlanTariff.plan_key == key))
            if row:
                continue
            s.add(
                PlanTariff(
                    plan_key=key,
                    name=p["name"],
                    description=p.get("description") or "",
                    emoji=p.get("emoji") or "📦",
                    months=int(p["months"]),
                    devices=int(p["devices"]),
                    price_rub=float(p["price_rub"]),
                    price_usdt=float(p["price_usdt"]),
                    popular=bool(p.get("popular")),
                    sort_order=i,
                    is_active=True,
                    tribute_link=None,
                    tribute_product_id=None,
                )
            )
            n += 1
        await s.commit()
    invalidate_catalog_cache()
    await message.answer(
        f"✅ Добавлено новых тарифов из встроенного каталога: <b>{n}</b>.\n"
        f"Уже существующие ключи не менялись. Правки цен — <code>/plan_add</code>.",
        parse_mode="HTML",
    )


@router.message(Command("plan_add"))
@admin_only
async def cmd_plan_add(message: Message):
    raw = (message.text or "").replace("/plan_add", "", 1).strip()
    if not raw:
        await message.answer(
            "Формат: <code>/plan_add {\"plan_key\":\"1m_1d\", …}</code>\n\n"
            "Обязательно: plan_key, name, months, devices, price_rub, price_usdt\n"
            "Опционально: description, emoji, popular (true/false), sort_order, is_active\n\n"
            "Пример:\n"
            "<pre>{\"plan_key\":\"1m_1d\",\"name\":\"Старт\",\"months\":1,\"devices\":1,"
            "\"price_rub\":100,\"price_usdt\":1.1,\"description\":\"1 мес · 1 устройство\","
            "\"emoji\":\"⚡\"}</pre>",
            parse_mode="HTML",
        )
        return
    try:
        data = _parse_plan_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        await message.answer(f"❌ Не разобрал JSON: {e}")
        return
    req = ("plan_key", "name", "months", "devices", "price_rub", "price_usdt")
    missing = [k for k in req if k not in data]
    if missing:
        await message.answer(f"❌ Нет полей: {', '.join(missing)}")
        return
    pk = str(data["plan_key"]).strip()
    if not re.match(r"^[a-zA-Z0-9_\-]{1,64}$", pk):
        await message.answer("❌ plan_key: только буквы, цифры, _, - (до 64 симв.)")
        return
    try:
        months = int(data["months"])
        devices = int(data["devices"])
        price_rub = float(data["price_rub"])
        price_usdt = float(data["price_usdt"])
    except (TypeError, ValueError):
        await message.answer("❌ months/devices — целые, price_rub/usdt — числа")
        return
    async with AsyncSessionLocal() as s:
        row = await s.scalar(select(PlanTariff).where(PlanTariff.plan_key == pk))
        if row:
            row.name = str(data["name"])
            row.description = str(data.get("description") or "")
            row.emoji = str(data.get("emoji") or "📦")[:16]
            row.months = months
            row.devices = devices
            row.price_rub = price_rub
            row.price_usdt = price_usdt
            row.popular = bool(data.get("popular"))
            if "sort_order" in data:
                row.sort_order = int(data["sort_order"])
            row.is_active = bool(data.get("is_active", True))
        else:
            s.add(
                PlanTariff(
                    plan_key=pk,
                    name=str(data["name"]),
                    description=str(data.get("description") or ""),
                    emoji=str(data.get("emoji") or "📦")[:16],
                    months=months,
                    devices=devices,
                    price_rub=price_rub,
                    price_usdt=price_usdt,
                    popular=bool(data.get("popular")),
                    sort_order=int(data.get("sort_order", 0)),
                    is_active=bool(data.get("is_active", True)),
                    tribute_link=None,
                    tribute_product_id=None,
                )
            )
        await s.commit()
    invalidate_catalog_cache()
    await message.answer(
        f"✅ Тариф <code>{pk}</code> сохранён. Проверь: кнопка «Купить» в боте.",
        parse_mode="HTML",
    )


@router.message(Command("plan_del"))
@admin_only
async def cmd_plan_del(message: Message):
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Формат: /plan_del plan_key")
        return
    pk = parts[1].strip()
    async with AsyncSessionLocal() as s:
        row = await s.scalar(select(PlanTariff).where(PlanTariff.plan_key == pk))
        if not row:
            await message.answer("❌ Такого ключа в БД нет.")
            return
        await s.delete(row)
        await s.commit()
    invalidate_catalog_cache()
    await message.answer(f"✅ Тариф <code>{pk}</code> удалён из БД.", parse_mode="HTML")


@router.message(Command("broadcast"))
@admin_only
async def cmd_broadcast(message: Message, bot: Bot):
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("Формат: /broadcast Текст сообщения")
        return
    if len(text) > 3500:
        text = text[:3497] + "..."
    async with AsyncSessionLocal() as s:
        users = (await s.execute(select(User).where(User.is_banned.is_(False)))).scalars().all()
    sent, failed = 0, 0
    batch = 0
    for user in users:
        try:
            await bot.send_message(user.tg_id, text, parse_mode="HTML")
            sent += 1
            batch += 1
            if batch >= 25:
                await asyncio.sleep(0.35)
                batch = 0
            else:
                await asyncio.sleep(0.06)
        except Exception:
            failed += 1
    await message.answer(f"📣 Рассылка завершена.\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}")


# ══════════════════════════════════════════════════════════════
#  FREEKASSA WEBHOOK (POST /freekassa/webhook)
#  Подключается через aiohttp web_app или отдельный FastAPI
# ══════════════════════════════════════════════════════════════

async def handle_freekassa_webhook(data: dict, bot: Bot, client_ip: str = ""):
    """
    Вызывается из HTTP-сервера при успешной оплате через Freekassa.
    data — словарь GET/POST-параметров от Freekassa.

    Freekassa ждёт ответ "YES" при успешной обработке.
    Повторяет запросы пока не получит "YES".
    IP серверов Freekassa: 168.119.157.136, 168.119.60.227, 178.154.197.79, 51.250.54.238
    """
    from utils.safe_log import freekassa_log_summary

    log.info("Freekassa webhook: %s", freekassa_log_summary(data, client_ip))

    # Проверяем подпись
    if not verify_freekassa_webhook(data, client_ip):
        log.error("Freekassa: неверная подпись")
        return {"status": "invalid_sign", "text": "NO"}

    # Проверяем статус — Freekassa шлёт только успешные (нет поля status в SCI)
    # но на всякий случай проверяем AMOUNT > 0
    try:
        amount = float(data.get("AMOUNT", 0))
    except ValueError:
        amount = 0
    if amount <= 0:
        log.error(f"Freekassa: сумма = {amount}")
        return {"status": "invalid_amount", "text": "NO"}

    order_id = data.get("MERCHANT_ORDER_ID", "")
    # Формат order_id: nina_<payment_id>_<tg_id>
    parts = order_id.split("_")
    if len(parts) < 3:
        log.error(f"Freekassa: неверный order_id: {order_id}")
        return {"status": "bad_order_id", "text": "NO"}

    try:
        payment_id = int(parts[1])
        tg_id      = int(parts[2])
    except ValueError:
        return {"status": "bad_order_id", "text": "NO"}

    async with AsyncSessionLocal() as s:
        payment = await s.scalar(select(Payment).where(Payment.id == payment_id))
        if not payment:
            log.error(f"Freekassa: платёж {payment_id} не найден")
            return {"status": "not_found", "text": "NO"}
        if payment.status == "confirmed":
            log.info(f"Freekassa: платёж {payment_id} уже обработан")
            return {"status": "already_done", "text": "YES"}  # YES чтобы Freekassa не повторял
        if payment.user_tg_id != tg_id:
            log.error("Freekassa: tg_id не совпадает с платежом")
            return {"status": "tg_mismatch", "text": "NO"}
        if payment.method != "card_ru":
            log.error("Freekassa: метод платежа не card_ru")
            return {"status": "bad_method", "text": "NO"}

        expected = float(payment.amount_rub or 0)
        if round(abs(amount - expected), 2) > FREEKASSA_AMOUNT_TOLERANCE:
            log.error(
                "Freekassa: сумма не совпадает: webhook=%s ожидалось=%s payment_id=%s",
                amount,
                expected,
                payment_id,
            )
            return {"status": "amount_mismatch", "text": "NO"}

        plan_key = payment.plan_key
        months = await _months_from_plan_key(plan_key)
        devices = payment.devices
        amount_rub_pay = payment.amount_rub or 0

        res = await s.execute(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == "pending")
            .values(status="processing")
        )
        await s.commit()
        if res.rowcount != 1:
            p2 = await s.scalar(select(Payment).where(Payment.id == payment_id))
            if p2 and p2.status == "confirmed":
                return {"status": "already_done", "text": "YES"}
            log.warning("Freekassa: не удалось захватить платёж %s (race)", payment_id)
            return {"status": "race", "text": "NO"}

    await issue_config(bot, tg_id, plan_key, devices, months, amount_rub_pay, payment_id)

    async with AsyncSessionLocal() as s:
        p3 = await s.scalar(select(Payment).where(Payment.id == payment_id))
        if not p3 or p3.status != "confirmed":
            await _revert_payment_processing(payment_id)
            log.error("Freekassa: выдача не завершилась, платёж %s возвращён в pending", payment_id)
            return {"status": "issue_failed", "text": "NO"}

    log.info(f"Freekassa: платёж {payment_id} успешно обработан для user {tg_id}")
    return {"status": "ok", "text": "YES"}


async def handle_tbank_webhook(data: dict, bot: Bot) -> dict:
    """
    POST JSON от Т-Банка на NotificationURL.
    Успешная обработка: HTTP 200, тело ровно OK (без HTML).
    """
    from services import tbank as tbank_svc

    pw = (settings.TBANK_PASSWORD or "").strip()
    if not pw:
        log.error("T-Bank webhook: TBANK_PASSWORD не задан")
        return {"ok": False, "http_status": 503}

    if not isinstance(data, dict):
        log.error("T-Bank webhook: ожидался JSON-объект")
        return {"ok": False, "http_status": 400}

    if not tbank_svc.verify_notification_token(data, pw):
        log.warning("T-Bank webhook: неверный Token")
        return {"ok": False, "http_status": 403}

    if not tbank_svc.notification_success_truthy(data.get("Success")):
        log.info("T-Bank webhook: Success=false, только подтверждение приёма")
        return {"ok": True, "text": "OK"}

    if not tbank_svc.notification_error_ok(data):
        log.info("T-Bank webhook: ErrorCode не 0, пропуск выдачи")
        return {"ok": True, "text": "OK"}

    status_u = str(data.get("Status") or "").strip().upper()
    if status_u != "CONFIRMED":
        log.info("T-Bank webhook: статус %s — выдача только по CONFIRMED", status_u)
        return {"ok": True, "text": "OK"}

    order_id = str(data.get("OrderId") or "")
    payment_id = tbank_svc.parse_payment_id_from_order_id(order_id)
    if payment_id is None:
        log.error("T-Bank webhook: неверный OrderId %r", order_id)
        return {"ok": True, "text": "OK"}

    try:
        amount_kop = int(str(data.get("Amount")))
    except (TypeError, ValueError):
        log.error("T-Bank webhook: нет корректного Amount")
        return {"ok": True, "text": "OK"}

    pay_pid = str(data.get("PaymentId") or "").strip()

    async with AsyncSessionLocal() as s:
        payment = await s.scalar(select(Payment).where(Payment.id == payment_id))
        if not payment:
            log.error("T-Bank: платёж %s не найден", payment_id)
            return {"ok": True, "text": "OK"}
        if payment.status == "confirmed":
            log.info("T-Bank: платёж %s уже подтверждён", payment_id)
            return {"ok": True, "text": "OK"}
        if payment.method != "tbank":
            log.error("T-Bank: метод платежа не tbank (payment %s)", payment_id)
            return {"ok": True, "text": "OK"}

        expected_kop = tbank_svc.rub_to_kopecks(float(payment.amount_rub or 0))
        if abs(amount_kop - expected_kop) > 1:
            log.error(
                "T-Bank: сумма в копейках webhook=%s ожидалось=%s payment_id=%s",
                amount_kop,
                expected_kop,
                payment_id,
            )
            return {"ok": True, "text": "OK"}

        stored_pid = (payment.tx_hash or "").strip()
        if stored_pid and pay_pid and stored_pid != pay_pid:
            log.error(
                "T-Bank: PaymentId не совпадает с Init payment_id=%s",
                payment_id,
            )
            return {"ok": True, "text": "OK"}

        tg_id = int(payment.user_tg_id)
        plan_key = payment.plan_key
        devices = payment.devices
        amount_rub_pay = float(payment.amount_rub or 0)

        months = await _months_from_plan_key(plan_key)

        res = await s.execute(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == "pending")
            .values(status="processing")
        )
        await s.commit()
        if res.rowcount != 1:
            p2 = await s.scalar(select(Payment).where(Payment.id == payment_id))
            if p2 and p2.status == "confirmed":
                return {"ok": True, "text": "OK"}
            if p2 and p2.status == "processing":
                return {"ok": True, "text": "OK"}
            log.warning("T-Bank: не удалось захватить платёж %s (race)", payment_id)
            return {"ok": True, "text": "OK"}

    await issue_config(bot, tg_id, plan_key, devices, months, amount_rub_pay, payment_id)

    async with AsyncSessionLocal() as s:
        p3 = await s.scalar(select(Payment).where(Payment.id == payment_id))
        if not p3 or p3.status != "confirmed":
            await _revert_payment_processing(payment_id)
            log.error("T-Bank: выдача не завершилась payment_id=%s", payment_id)
            return {"ok": False, "http_status": 500}

    log.info("T-Bank: платёж %s подтверждён user=%s", payment_id, tg_id)
    return {"ok": True, "text": "OK"}


# ══════════════════════════════════════════════════════════════
#  ADMIN: управление пользователями
# ══════════════════════════════════════════════════════════════

@router.message(Command("ban"))
@admin_only
async def cmd_ban(message: Message, bot: Bot):
    """Формат: /ban <tg_id> [причина]"""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Формат: /ban <tg_id> [причина]")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("tg_id должен быть числом")
        return

    async with AsyncSessionLocal() as s:
        user = await s.scalar(select(User).where(User.tg_id == target_id))
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        user.is_banned = True
        # Деактивируем все его подписки
        subs = (await s.execute(
            select(Subscription).where(Subscription.user_tg_id == target_id)
        )).scalars().all()
        for sub in subs:
            sub.is_active = False
        await s.commit()

    await get_vpn_panel().disable_client(target_id)

    reason = parts[2] if len(parts) > 2 else "Нарушение правил"
    try:
        await bot.send_message(target_id, f"⛔ Ваш аккаунт заблокирован.\nПричина: {reason}")
    except Exception:
        pass
    await message.answer(f"✅ Пользователь {target_id} заблокирован. Причина: {reason}")


@router.message(Command("unban"))
@admin_only
async def cmd_unban(message: Message):
    """Формат: /unban <tg_id>"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Формат: /unban <tg_id>")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("tg_id должен быть числом")
        return

    async with AsyncSessionLocal() as s:
        user = await s.scalar(select(User).where(User.tg_id == target_id))
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        user.is_banned = False
        await s.commit()
    await message.answer(f"✅ Пользователь {target_id} разблокирован")


@router.message(Command("give"))
@admin_only
async def cmd_give(message: Message, bot: Bot):
    """Формат: /give <tg_id> <plan_key>  — выдать подписку вручную"""
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Формат: /give <tg_id> <plan_key>\nПример: /give 123456789 6m_3d")

        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("tg_id должен быть числом")
        return

    plan_key = parts[2]
    plans = await get_plans_catalog()
    if plan_key not in plans:
        await message.answer(f"Неизвестный план. Доступные: {list(plans.keys())}")
        return

    plan = plans[plan_key]
    # Создаём фиктивный payment record
    async with AsyncSessionLocal() as s:
        payment = Payment(
            user_tg_id=target_id, plan_key=plan_key,
            devices=plan["devices"], method="manual",
            amount_rub=0, currency="RUB", status="pending",
        )
        s.add(payment)
        await s.commit()
        await s.refresh(payment)
        pid = payment.id

    await issue_config(bot, target_id, plan_key, plan["devices"], plan["months"], 0, pid)
    await message.answer(f"✅ Подписка {plan_key} выдана пользователю {target_id}")


@router.message(Command("delete_user"))
@admin_only
async def cmd_delete_user(message: Message):
    """Формат: /delete_user <tg_id> — удалить клиента из панели VPN"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Формат: /delete_user <tg_id>")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("tg_id должен быть числом")
        return

    ok = await get_vpn_panel().delete_client(target_id)
    await message.answer(
        f"{'✅' if ok else '⚠️'} Клиент в панели для user {target_id}: "
        f"{'удалён' if ok else 'не удалось удалить (проверьте логи)'}"
    )