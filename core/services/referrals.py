"""SaaS referral: invitee applies a code; referrer gets +7 days after first paid sub."""
from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.enums import PaymentStatus
from infrastructure.db.models import Payment, User

log = logging.getLogger(__name__)

REFERRAL_BONUS_DAYS = 7
INVITEE_BONUS_DAYS = 7


def referral_code_for(user: User) -> str:
    return f"nv{user.panel_user_key}"


def parse_referral_key(raw: str) -> str:
    """Accept nv123, 123, or https://ninavpn.store/?ref=nv123 → panel key digits."""
    s = (raw or "").strip()
    if not s:
        return ""
    if "ref=" in s.lower() or s.lower().startswith("http"):
        try:
            parsed = urlparse(s)
            q = parse_qs(parsed.query)
            if q.get("ref"):
                s = q["ref"][0]
        except Exception:
            pass
    s = s.strip()
    if s.lower().startswith("nv"):
        s = s[2:]
    return s.strip()


async def _bot_tg_has_paid(tg_id: int) -> bool:
    """Telegram-bot purchases live in a separate DB — same person cannot be invited."""
    try:
        from database import AsyncSessionLocal
        from database import Payment as BotPayment

        async with AsyncSessionLocal() as bot_session:
            row = await bot_session.scalar(
                select(BotPayment.id)
                .where(
                    BotPayment.user_tg_id == int(tg_id),
                    BotPayment.status == "confirmed",
                )
                .limit(1)
            )
            return row is not None
    except Exception:
        log.debug("bot referral paid-check skipped tg_id=%s", tg_id, exc_info=True)
        return False


async def user_has_paid(session: AsyncSession, user_id: UUID) -> bool:
    """
    True if this identity ever bought a subscription (app payment, or Telegram bot
    payment on the same tg_id). Login-only accounts stay eligible to be invited.
    """
    user = await session.get(User, user_id)
    if not user:
        return False
    row = await session.scalar(
        select(Payment.id).where(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.CONFIRMED.value,
        ).limit(1)
    )
    if row is not None:
        return True
    if user.tg_id:
        return await _bot_tg_has_paid(int(user.tg_id))
    return False


async def _add_days_to_user(session: AsyncSession, user: User, days: int) -> None:
    """Stack `days` onto the latest sub, or create limited VPN access if none exists."""
    if days <= 0:
        return
    from core.services.welcome_access import grant_bonus_days

    await grant_bonus_days(session, user, days)


async def grant_referrer_bonus_for_payment(
    session: AsyncSession, *, payer_user_id: UUID
) -> bool:
    """
    After the invitee's first confirmed payment:
    referrer +REFERRAL_BONUS_DAYS, invitee +INVITEE_BONUS_DAYS (stacked).
    Idempotent via referral_rewarded_at.
    """
    invitee = await session.get(User, payer_user_id)
    if not invitee or not invitee.referrer_id:
        return False
    if getattr(invitee, "referral_rewarded_at", None):
        return False

    referrer = await session.get(User, invitee.referrer_id)
    if not referrer or referrer.id == invitee.id:
        return False

    await _add_days_to_user(session, referrer, REFERRAL_BONUS_DAYS)
    await _add_days_to_user(session, invitee, INVITEE_BONUS_DAYS)

    invitee.referral_rewarded_at = datetime.utcnow()
    await session.commit()
    log.info(
        "referral bonus referrer=%s +%sd invitee=%s +%sd",
        referrer.id,
        REFERRAL_BONUS_DAYS,
        invitee.id,
        INVITEE_BONUS_DAYS,
    )
    return True
