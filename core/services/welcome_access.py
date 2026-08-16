"""Launch access: every new cabinet user gets 3 months of VPN on a limited node set."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.domain.enums import SubscriptionStatus
from core.services.config_links import apply_links_to_subscription, read_links_from_subscription
from core.services.network_locations import (
    WELCOME_LOCATION_KEYS,
    expand_share_links,
    filter_nodes_by_locations,
    match_uri_to_node,
)
from infrastructure.db.models import Plan, Subscription, User

log = logging.getLogger(__name__)

WELCOME_PLAN_KEY = "welcome_3m"
WELCOME_MONTHS = 3
WELCOME_DEVICES = 1
WELCOME_DAYS = WELCOME_MONTHS * 30

_locks: dict[str, asyncio.Lock] = {}
_bg_tasks: dict[str, asyncio.Task] = {}


def _lock_for(user_id: UUID) -> asyncio.Lock:
    key = str(user_id)
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


def is_welcome_plan(plan: Optional[Plan]) -> bool:
    return bool(plan and plan.plan_key == WELCOME_PLAN_KEY)


async def ensure_welcome_plan(session: AsyncSession) -> Plan:
    row = await session.scalar(select(Plan).where(Plan.plan_key == WELCOME_PLAN_KEY))
    if row:
        return row
    row = Plan(
        plan_key=WELCOME_PLAN_KEY,
        name="3 месяца",
        description="Бесплатный доступ после регистрации",
        months=WELCOME_MONTHS,
        devices=WELCOME_DEVICES,
        price_rub=0,
        is_active=False,
        sort_order=0,
    )
    session.add(row)
    await session.flush()
    return row


def _panel_for_welcome():
    from config import settings, xui_nodes_from_settings
    from services.vpn_panel import get_vpn_panel

    backend = (getattr(settings, "VPN_BACKEND", None) or "").lower().strip()
    if backend != "xui":
        return get_vpn_panel()
    nodes = xui_nodes_from_settings(settings)
    selected = filter_nodes_by_locations(nodes, WELCOME_LOCATION_KEYS)
    if not selected:
        log.warning("welcome access: no XUI nodes matched %s — using all nodes", WELCOME_LOCATION_KEYS)
        return get_vpn_panel()
    from services.xui_panel import MultiXuiPanel, XuiPanel

    if len(selected) == 1:
        return XuiPanel(selected[0])
    return MultiXuiPanel(selected)


async def _filter_welcome_links(links: list[str]) -> list[str]:
    from config import settings, xui_nodes_from_settings

    uris = await expand_share_links(links)
    nodes = filter_nodes_by_locations(xui_nodes_from_settings(settings), WELCOME_LOCATION_KEYS)
    if not nodes:
        return [u for u in uris if u.startswith(("vless://", "vmess://", "trojan://", "ss://"))]
    kept: list[str] = []
    seen: set[str] = set()
    for uri in uris:
        if not uri.startswith(("vless://", "vmess://", "trojan://", "ss://")):
            continue
        node = match_uri_to_node(uri, nodes)
        if not node:
            continue
        if uri in seen:
            continue
        seen.add(uri)
        kept.append(uri)
    return kept


async def provision_limited_vpn(
    *,
    user: User,
    months: int = 0,
    days: int = 0,
    devices: int = WELCOME_DEVICES,
) -> dict:
    """Create/extend the panel client only on welcome locations."""
    panel = _panel_for_welcome()
    username = (user.email or "").split("@")[0] or None
    key = int(user.panel_user_key)
    result: dict = {}
    if months > 0:
        result = await panel.create_or_extend_subscription(
            key, months, devices, tg_username=username
        )
        expires = None
        expiry_ms = result.get("expiry_ms")
        if expiry_ms:
            try:
                expires = datetime.utcfromtimestamp(int(expiry_ms) / 1000.0)
            except Exception:
                expires = None
        if expires is None:
            try:
                expires = await panel.get_subscription_expiry(key)
            except Exception:
                expires = None
        if expires is None:
            expires = datetime.utcnow() + timedelta(days=30 * months)
        links = list(result.get("links") or [])
        if result.get("subscription_url"):
            links.append(result["subscription_url"])
        filtered = await _filter_welcome_links(links)
        if not filtered:
            # Panel already limited to welcome nodes — keep whatever we got.
            filtered = [
                u
                for u in await expand_share_links(links)
                if u.startswith(("vless://", "vmess://", "trojan://", "ss://"))
            ] or [L for L in links if L]
        return {
            "uuid": result.get("uuid"),
            "links": filtered,
            "expires_at": expires,
        }

    d = max(1, int(days or WELCOME_DAYS))
    granted = await panel.grant_free_days(key, d, devices)
    if not granted.get("ok"):
        # Client may not exist yet — create with 0 months then extend.
        await panel.create_or_extend_subscription(key, 0, devices, tg_username=username)
        granted = await panel.grant_free_days(key, d, devices)
    links = list(granted.get("links") or [])
    if granted.get("subscription_url"):
        links.append(granted["subscription_url"])
    filtered = await _filter_welcome_links(links)
    if not filtered:
        filtered = [
            u
            for u in await expand_share_links(links)
            if u.startswith(("vless://", "vmess://", "trojan://", "ss://"))
        ] or [L for L in links if L]
    expires = granted.get("expires")
    if not isinstance(expires, datetime):
        expires = datetime.utcnow() + timedelta(days=d)
    return {
        "uuid": granted.get("uuid"),
        "links": filtered,
        "expires_at": expires,
    }


def needs_welcome_provision(sub: Optional[Subscription]) -> bool:
    if sub is None:
        return True
    if not is_welcome_plan(sub.plan):
        return False
    if sub.expires_at and sub.expires_at <= datetime.utcnow():
        return False
    links = read_links_from_subscription(sub)
    if not links:
        return True
    if sub.status in (
        SubscriptionStatus.PROVISIONING.value,
        SubscriptionStatus.PAST_DUE.value,
    ):
        return True
    return False


async def _latest(session: AsyncSession, user_id: UUID) -> Optional[Subscription]:
    return await session.scalar(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .options(selectinload(Subscription.plan))
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )


async def ensure_welcome_row(session: AsyncSession, user: User) -> Optional[Subscription]:
    """
    First login only: create a 3-month trial row in DB (no panel I/O).
    Existing paid/expired subscriptions are left untouched.
    """
    async with _lock_for(user.id):
        sub = await _latest(session, user.id)
        if sub is not None:
            return sub
        plan = await ensure_welcome_plan(session)
        now = datetime.utcnow()
        sub = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status=SubscriptionStatus.TRIAL.value,
            devices=WELCOME_DEVICES,
            months=WELCOME_MONTHS,
            started_at=now,
            expires_at=now + timedelta(days=WELCOME_DAYS),
        )
        session.add(sub)
        await session.commit()
        created = await _latest(session, user.id)
        log.info("welcome row created user=%s until=%s", user.id, created.expires_at if created else None)
        return created


async def _apply_result(sub: Subscription, result: dict) -> None:
    links = result.get("links") or []
    primary = links[0] if links else None
    apply_links_to_subscription(sub, links, primary=primary)
    sub.status = SubscriptionStatus.TRIAL.value
    sub.panel_uuid = result.get("uuid") or sub.panel_uuid
    sub.started_at = sub.started_at or datetime.utcnow()
    if result.get("expires_at"):
        sub.expires_at = result["expires_at"]
    sub.disabled_at = None


async def ensure_welcome_access(session: AsyncSession, user: User) -> Optional[Subscription]:
    """
    If the user has never had a subscription, provision 3 months on welcome nodes.
    Idempotent. Does not refresh expired or paid plans.
    Panel I/O runs without holding the DB lock so /subscriptions/me stays fast.
    """
    sub = await ensure_welcome_row(session, user)
    if not needs_welcome_provision(sub):
        return sub
    try:
        result = await asyncio.wait_for(
            provision_limited_vpn(
                user=user, months=WELCOME_MONTHS, devices=WELCOME_DEVICES
            ),
            timeout=90,
        )
        if not result.get("links"):
            log.warning("welcome provision returned no node links user=%s", user.id)
            return sub
        async with _lock_for(user.id):
            sub = await _latest(session, user.id) or sub
            await _apply_result(sub, result)
            if not sub.expires_at:
                sub.expires_at = datetime.utcnow() + timedelta(days=WELCOME_DAYS)
            await session.commit()
            granted = await _latest(session, user.id)
            log.info(
                "welcome access granted user=%s until=%s links=%s",
                user.id,
                granted.expires_at if granted else None,
                len(result.get("links") or []),
            )
            return granted
    except Exception:
        log.exception("welcome access failed user=%s", user.id)
        return await _latest(session, user.id) or sub


async def grant_bonus_days(session: AsyncSession, user: User, days: int) -> Optional[Subscription]:
    """Stack `days` onto the latest sub, or create limited VPN access if none exists."""
    if days <= 0:
        return await _latest(session, user.id)
    now = datetime.utcnow()
    sub = await _latest(session, user.id)
    if sub:
        base = sub.expires_at if sub.expires_at and sub.expires_at > now else now
        sub.expires_at = base + timedelta(days=days)
        if sub.status in (
            SubscriptionStatus.EXPIRED.value,
            SubscriptionStatus.CANCELLED.value,
            SubscriptionStatus.PAST_DUE.value,
            SubscriptionStatus.PROVISIONING.value,
        ):
            # Keep trial if this was unpaid welcome access; otherwise mark active.
            sub.status = (
                SubscriptionStatus.TRIAL.value
                if is_welcome_plan(sub.plan)
                else SubscriptionStatus.ACTIVE.value
            )
            sub.disabled_at = None
        try:
            from adapters.vpn.xui_adapter import get_vpn_adapter

            ok = await get_vpn_adapter().extend_by_days(user.panel_user_key, days)
            if not ok and not read_links_from_subscription(sub):
                result = await provision_limited_vpn(user=user, days=days)
                await _apply_result(sub, result)
                if sub.expires_at and sub.expires_at < now + timedelta(days=days):
                    sub.expires_at = now + timedelta(days=days)
        except Exception:
            log.exception("bonus panel extend failed user=%s days=%s", user.id, days)
        await session.flush()
        return sub

    plan = await ensure_welcome_plan(session)
    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.PROVISIONING.value,
        devices=WELCOME_DEVICES,
        months=0,
        started_at=now,
        expires_at=now + timedelta(days=days),
    )
    session.add(sub)
    await session.flush()
    try:
        result = await provision_limited_vpn(user=user, days=days)
        if not result.get("links"):
            raise RuntimeError("bonus provision returned no node links")
        await _apply_result(sub, result)
        sub.expires_at = now + timedelta(days=days)
        await session.flush()
        log.info("bonus-only VPN user=%s days=%s", user.id, days)
        return sub
    except Exception:
        log.exception("bonus-only VPN failed user=%s", user.id)
        sub.status = SubscriptionStatus.PAST_DUE.value
        await session.flush()
        return sub


def schedule_welcome_access(user_id: UUID) -> None:
    """Fire-and-forget: never attach to the HTTP response (that froze register/login)."""
    key = str(user_id)
    existing = _bg_tasks.get(key)
    if existing is not None and not existing.done():
        return
    try:
        task = asyncio.create_task(grant_welcome_in_background(user_id), name=f"welcome:{key}")
    except RuntimeError:
        log.warning("welcome grant: no running event loop user=%s", user_id)
        return
    _bg_tasks[key] = task

    def _cleanup(done: asyncio.Task) -> None:
        _bg_tasks.pop(key, None)
        try:
            exc = done.exception()
        except asyncio.CancelledError:
            return
        except Exception:
            return
        if exc:
            log.exception("welcome background task failed user=%s", user_id, exc_info=exc)

    task.add_done_callback(_cleanup)


async def grant_welcome_in_background(user_id: UUID) -> None:
    from infrastructure.db.base import SaasSessionLocal

    try:
        async with SaasSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return
            await ensure_welcome_access(session, user)
    except Exception:
        log.exception("background welcome grant failed user=%s", user_id)
