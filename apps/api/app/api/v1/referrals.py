from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.deps import CurrentUser, SessionDep
from core.services.referrals import (
    INVITEE_BONUS_DAYS,
    REFERRAL_BONUS_DAYS,
    parse_referral_key,
    referral_code_for,
    user_has_paid,
)
from core.settings import saas_settings
from infrastructure.db.models import User

log = logging.getLogger(__name__)

router = APIRouter()


def referral_link_for(user: User) -> str:
    base = (saas_settings.SAAS_PUBLIC_BASE_URL or "https://ninavpn.store").rstrip("/")
    return f"{base}/?ref={referral_code_for(user)}"


class ReferralMeOut(BaseModel):
    code: str
    link: str
    bonus_days: int = REFERRAL_BONUS_DAYS
    invitee_bonus_days: int = INVITEE_BONUS_DAYS
    invited_count: int = 0
    referrer_code: Optional[str] = None
    can_apply: bool = True
    rewarded: bool = False


class ApplyReferralRequest(BaseModel):
    code: str = Field(min_length=3, max_length=64)


class AffiliateMeOut(BaseModel):
    code: str
    link: str
    commission_percent: float = 20.0
    payout: str = "crypto_or_balance_days"
    invited_count: int = 0
    note: str = "Affiliate payouts are tracked; contact support to cash out."


async def _referral_payload(session: AsyncSession, user: User) -> ReferralMeOut:
    invited = await session.scalar(
        select(func.count()).select_from(User).where(User.referrer_id == user.id)
    )
    referrer_code = None
    if user.referrer_id:
        ref = await session.get(User, user.referrer_id)
        if ref:
            referrer_code = referral_code_for(ref)
    paid = False
    try:
        paid = await user_has_paid(session, user.id)
    except Exception:
        log.exception("referral paid-check failed user=%s", user.id)
    can_apply = not bool(user.referrer_id) and not paid
    return ReferralMeOut(
        code=referral_code_for(user),
        link=referral_link_for(user),
        bonus_days=REFERRAL_BONUS_DAYS,
        invitee_bonus_days=INVITEE_BONUS_DAYS,
        invited_count=int(invited or 0),
        referrer_code=referrer_code,
        can_apply=can_apply,
        rewarded=bool(getattr(user, "referral_rewarded_at", None)),
    )


@router.get("/me", response_model=ReferralMeOut)
async def referral_me(user: CurrentUser, session: SessionDep):
    return await _referral_payload(session, user)


@router.post("/apply", response_model=ReferralMeOut)
async def apply_referral(body: ApplyReferralRequest, user: CurrentUser, session: SessionDep):
    if user.referrer_id:
        raise HTTPException(status_code=400, detail="referrer_already_set")
    if await user_has_paid(session, user.id):
        raise HTTPException(status_code=400, detail="already_paid")
    raw = parse_referral_key(body.code)
    try:
        key = int(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid_code") from e

    referrer = await session.scalar(select(User).where(User.panel_user_key == key))
    if not referrer or referrer.id == user.id:
        raise HTTPException(status_code=400, detail="invalid_code")

    db_user = await session.get(User, user.id)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid user")
    if db_user.referrer_id:
        raise HTTPException(status_code=400, detail="referrer_already_set")
    db_user.referrer_id = referrer.id
    await session.commit()
    await session.refresh(db_user)
    return await _referral_payload(session, db_user)


@router.get("/affiliate", response_model=AffiliateMeOut)
async def affiliate_me(user: CurrentUser, session: SessionDep):
    invited = await session.scalar(
        select(func.count()).select_from(User).where(User.referrer_id == user.id)
    )
    return AffiliateMeOut(
        code=referral_code_for(user),
        link=referral_link_for(user),
        invited_count=int(invited or 0),
    )
