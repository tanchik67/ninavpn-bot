
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from apps.api.app.deps import CurrentUser, SessionDep, client_ip
from apps.api.app.schemas import CheckoutResponse, ConfigOut, SubscriptionOut
from core.domain.enums import SubscriptionStatus
from core.services.billing import create_checkout, latest_subscription
from core.services.qr import build_deeplinks

router = APIRouter()


@router.get("/me", response_model=Optional[SubscriptionOut])
async def my_subscription(user: CurrentUser, session: SessionDep):
    sub = await latest_subscription(session, user.id)
    if not sub:
        return None
    plan = sub.plan
    return SubscriptionOut(
        id=sub.id,
        status=sub.status,
        devices=sub.devices,
        months=sub.months,
        plan_key=plan.plan_key if plan else None,
        plan_name=plan.name if plan else None,
        started_at=sub.started_at,
        expires_at=sub.expires_at,
        has_config=bool(sub.config_link or sub.config_qr),
    )


@router.get("/me/config", response_model=ConfigOut)
async def my_config(user: CurrentUser, session: SessionDep):
    sub = await latest_subscription(session, user.id)
    if not sub or sub.status not in (
        SubscriptionStatus.ACTIVE.value,
        SubscriptionStatus.PAST_DUE.value,
    ):
        raise HTTPException(status_code=404, detail="no_active_subscription")
    links = [L for L in [sub.config_link, sub.config_link_extra] if L]
    sub_url = sub.config_link
    # Prefer subscription URL style if it looks like http
    if sub.config_link and sub.config_link.startswith("http"):
        sub_url = sub.config_link
    elif links:
        sub_url = links[0]
    return ConfigOut(
        subscription_url=sub_url,
        links=links,
        qr_base64=sub.config_qr,
        deeplinks=build_deeplinks(sub_url) if sub_url else {},
        expires_at=sub.expires_at,
        status=sub.status,
    )


@router.post("/me/renew", response_model=CheckoutResponse)
async def renew(user: CurrentUser, session: SessionDep, request: Request):
    sub = await latest_subscription(session, user.id)
    if not sub or not sub.plan:
        raise HTTPException(status_code=400, detail="no_subscription_to_renew")
    payment, url = await create_checkout(
        session,
        user=user,
        plan_key=sub.plan.plan_key,
        ip=client_ip(request),
    )
    return CheckoutResponse(
        payment_id=payment.id,
        payment_url=url,
        provider=payment.provider,
        status=payment.status,
        checkout_token=payment.checkout_token,
    )
