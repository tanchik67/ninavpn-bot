"""
Планировщик: проверка истекающих подписок и отправка напоминаний.
Запускается при старте бота через asyncio.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import select, update

from config import settings
from database import Subscription, AsyncSessionLocal
from keyboards.inline import kb_plans
from services.catalog import get_plans_catalog
from utils.texts import txt_reminder

log = logging.getLogger(__name__)


async def check_expiring_subscriptions(bot: Bot):
    """Одно напоминание на пользователя: по всем скоро истекающим активным подпискам."""
    remind_dt = datetime.utcnow() + timedelta(days=settings.REMIND_DAYS_BEFORE)
    now = datetime.utcnow()

    async with AsyncSessionLocal() as s:
        subs = (await s.execute(
            select(Subscription).where(
                Subscription.is_active == True,
                Subscription.reminded == False,
                Subscription.expires_at <= remind_dt,
                Subscription.expires_at > now,
            )
        )).scalars().all()

        by_user: dict[int, list[Subscription]] = {}
        for sub in subs:
            by_user.setdefault(sub.user_tg_id, []).append(sub)

        plans = await get_plans_catalog()
        for uid, user_subs in by_user.items():
            canonical = max(user_subs, key=lambda x: x.expires_at or now)
            days_left = (canonical.expires_at - now).days if canonical.expires_at else 0
            expires_str = canonical.expires_at.strftime("%d.%m.%Y") if canonical.expires_at else "—"
            try:
                await bot.send_message(
                    uid,
                    txt_reminder(days_left, expires_str),
                    reply_markup=kb_plans(plans),
                    parse_mode="HTML",
                )
                log.info(f"Напоминание отправлено: user={uid}, sub={canonical.id}")
            except Exception as e:
                log.warning(f"Не удалось отправить напоминание user={uid}: {e}")

            for sub in user_subs:
                await s.execute(
                    update(Subscription)
                    .where(Subscription.id == sub.id)
                    .values(reminded=True)
                )

        await s.commit()


async def deactivate_expired(bot: Bot):
    """Деактивирует истёкшие подписки и отключает клиента в панели VPN."""
    from services.vpn_panel import get_vpn_panel

    panel = get_vpn_panel()
    user_ids: set[int] = set()

    async with AsyncSessionLocal() as s:
        subs = (await s.execute(
            select(Subscription).where(
                Subscription.is_active == True,
                Subscription.expires_at <= datetime.utcnow(),
            )
        )).scalars().all()

        plans = await get_plans_catalog()
        for sub in subs:
            user_ids.add(sub.user_tg_id)
            await s.execute(
                update(Subscription)
                .where(Subscription.id == sub.id)
                .values(is_active=False)
            )
            log.info(f"Подписка #{sub.id} деактивирована")
            try:
                await bot.send_message(
                    sub.user_tg_id,
                    "⚠️ <b>Твоя подписка истекла.</b>\n\n"
                    "Продли прямо сейчас — не теряй доступ к серверам!",
                    reply_markup=kb_plans(plans),
                    parse_mode="HTML",
                )
            except Exception:
                pass

        await s.commit()

    for uid in user_ids:
        try:
            await panel.disable_client(uid)
        except Exception as e:
            log.warning("Панель: не удалось отключить user %s: %s", uid, e)


async def scheduler_loop(bot: Bot):
    """Основной цикл планировщика — запускается раз в час."""
    log.info("Планировщик запущен")
    while True:
        try:
            await check_expiring_subscriptions(bot)
            await deactivate_expired(bot)
        except Exception as e:
            log.error(f"Ошибка планировщика: {e}")
        await asyncio.sleep(3600)   # каждый час
