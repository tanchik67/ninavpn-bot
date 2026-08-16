from datetime import datetime
from typing import Optional
import logging

from fastapi import APIRouter, HTTPException, Request

from apps.api.app.deps import CurrentUser, SessionDep, client_ip
from apps.api.app.schemas import CheckoutResponse, ConfigNodeOut, ConfigOut, SubscriptionOut
from core.domain.enums import SubscriptionStatus
from core.services.billing import create_checkout, latest_subscription, subscription_allows_vpn
from core.services.config_links import read_links_from_subscription
from core.services.network_locations import (
    WELCOME_LOCATION_KEYS,
    build_node_configs,
    filter_config_nodes,
)
from core.services.qr import build_deeplinks
from core.services.welcome_access import (
    ensure_welcome_row,
    is_welcome_plan,
    needs_welcome_provision,
    schedule_welcome_access,
)

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/me", response_model=Optional[SubscriptionOut])
async def my_subscription(user: CurrentUser, session: SessionDep):
    try:
        sub = await ensure_welcome_row(session, user)
    except Exception:
        log.exception("welcome row failed user=%s", user.id)
        sub = await latest_subscription(session, user.id)
    if needs_welcome_provision(sub):
        schedule_welcome_access(user.id)
    if not sub:
        return None
    plan = sub.plan
    live = subscription_allows_vpn(sub)
    status = sub.status
    if sub.expires_at and sub.expires_at <= datetime.utcnow():
        status = SubscriptionStatus.EXPIRED.value
    return SubscriptionOut(
        id=sub.id,
        status=status,
        devices=sub.devices,
        months=sub.months,
        plan_key=plan.plan_key if plan else None,
        plan_name=plan.name if plan else None,
        started_at=sub.started_at,
        expires_at=sub.expires_at,
        has_config=live,
    )


@router.get("/me/config", response_model=ConfigOut)
async def my_config(
    user: CurrentUser,
    session: SessionDep,
    include_qr: bool = False,
):
    """
    Subscription share links + per-node URIs for the app.

    QR base64 is omitted by default — it can be hundreds of KB and stalls
    mobile clients on slow links. Pass include_qr=true for the Config screen.
    """
    sub = await latest_subscription(session, user.id)
    if needs_welcome_provision(sub):
        schedule_welcome_access(user.id)
    if not subscription_allows_vpn(sub):
        raise HTTPException(status_code=404, detail="no_active_subscription")
    links = read_links_from_subscription(sub)
    limited = is_welcome_plan(sub.plan)
    nodes_raw = await build_node_configs(links)
    if limited:
        nodes_raw = filter_config_nodes(nodes_raw, WELCOME_LOCATION_KEYS)
        links = [n["uri"] for n in nodes_raw if n.get("uri")]
    nodes = [ConfigNodeOut(**n) for n in nodes_raw]
    sub_url = None
    if not limited:
        if sub.config_link and sub.config_link.startswith("http"):
            sub_url = sub.config_link
        elif links:
            sub_url = next((L for L in links if L.startswith("http")), links[0] if links else None)
    elif links:
        sub_url = links[0]

    return ConfigOut(
        subscription_url=sub_url,
        links=links,
        nodes=nodes,
        qr_base64=(sub.config_qr if include_qr else None),
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
