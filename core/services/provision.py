from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.notifications.dispatcher import NotificationDispatcher
from adapters.vpn.xui_adapter import get_vpn_adapter
from core.domain.enums import (
    NotificationChannel,
    NotificationOutboxStatus,
    PaymentStatus,
    ProvisionJobStatus,
    SubscriptionStatus,
)
from core.ports.notifications import NotificationMessage
from core.services.audit import write_audit
from core.services.qr import build_deeplinks, make_qr_base64
from infrastructure.db.models import (
    NotificationOutbox,
    Payment,
    Plan,
    ProvisionJob,
    Subscription,
    User,
)
from services.vpn_panel import client_email

log = logging.getLogger(__name__)


async def run_provision_for_payment(session: AsyncSession, payment_id: int) -> Subscription:
    job = await session.scalar(select(ProvisionJob).where(ProvisionJob.payment_id == payment_id))
    if not job:
        job = ProvisionJob(payment_id=payment_id, status=ProvisionJobStatus.QUEUED.value)
        session.add(job)
        await session.flush()

    if job.status == ProvisionJobStatus.SUCCEEDED.value:
        payment = await session.get(Payment, payment_id)
        if payment and payment.subscription_id:
            sub = await session.get(Subscription, payment.subscription_id)
            if sub:
                return sub

    job.status = ProvisionJobStatus.RUNNING.value
    job.attempts = int(job.attempts or 0) + 1
    await session.commit()

    payment = await session.get(Payment, payment_id)
    if not payment:
        raise RuntimeError(f"payment {payment_id} not found")
    if payment.status != PaymentStatus.CONFIRMED.value:
        raise RuntimeError(f"payment {payment_id} not confirmed")

    user = await session.get(User, payment.user_id)
    plan = await session.get(Plan, payment.plan_id)
    if not user or not plan:
        raise RuntimeError("user/plan missing")

    # Create or reuse subscription row in provisioning state
    sub: Optional[Subscription] = None
    if payment.subscription_id:
        sub = await session.get(Subscription, payment.subscription_id)
    if sub is None:
        sub = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status=SubscriptionStatus.PROVISIONING.value,
            devices=plan.devices,
            months=plan.months,
            started_at=datetime.utcnow(),
        )
        session.add(sub)
        await session.flush()
        payment.subscription_id = sub.id
        await session.commit()

    vpn = get_vpn_adapter()
    username = user.email.split("@")[0]
    try:
        result = await vpn.provision(
            panel_user_key=user.panel_user_key,
            months=plan.months,
            devices=plan.devices,
            username=username,
        )
    except Exception as e:
        job.status = ProvisionJobStatus.FAILED.value
        job.last_error = str(e)[:2000]
        job.finished_at = datetime.utcnow()
        sub.status = SubscriptionStatus.PAST_DUE.value
        await write_audit(
            session,
            action="provision.failed",
            entity_type="payment",
            entity_id=str(payment_id),
            actor_user_id=user.id,
            meta={"error": str(e)[:500]},
        )
        await session.commit()
        raise

    links = result.links or []
    primary = links[0] if links else (result.subscription_url or "")
    extra = links[1] if len(links) > 1 else None
    qr = make_qr_base64(primary) if primary else None

    sub.status = SubscriptionStatus.ACTIVE.value
    sub.panel_uuid = result.uuid
    sub.panel_client_email = client_email(user.panel_user_key, username)
    sub.config_link = primary or result.subscription_url
    sub.config_link_extra = extra
    sub.config_qr = qr
    sub.started_at = sub.started_at or datetime.utcnow()
    sub.expires_at = result.expires_at
    sub.disabled_at = None

    job.status = ProvisionJobStatus.SUCCEEDED.value
    job.finished_at = datetime.utcnow()
    job.last_error = None

    # Outbox notification
    payload = {
        "subscription_url": result.subscription_url or primary,
        "links": links,
        "deeplinks": build_deeplinks(result.subscription_url or primary) if (result.subscription_url or primary) else {},
        "expires_at": result.expires_at.isoformat() if result.expires_at else None,
    }
    channel = NotificationChannel.TELEGRAM if user.tg_id else NotificationChannel.EMAIL
    recipient = str(user.tg_id) if user.tg_id else user.email
    body = (
        f"✅ NinaVPN готов!\n"
        f"Подписка до: {payload['expires_at'] or '—'}\n"
        f"Ссылка: {payload['subscription_url']}"
    )
    session.add(
        NotificationOutbox(
            user_id=user.id,
            channel=channel.value,
            template="access_ready",
            payload=payload,
            status=NotificationOutboxStatus.PENDING.value,
        )
    )

    await write_audit(
        session,
        action="provision.succeeded",
        entity_type="subscription",
        entity_id=str(sub.id),
        actor_user_id=user.id,
        meta={"payment_id": payment_id},
    )
    await session.commit()

    # Best-effort immediate notify
    try:
        dispatcher = NotificationDispatcher()
        ok = await dispatcher.dispatch(
            NotificationMessage(
                channel=channel,
                template="access_ready",
                recipient=recipient,
                subject="NinaVPN — доступ готов",
                body=body,
                payload=payload,
            )
        )
        if ok:
            # Avoid double-send by worker outbox flush
            from sqlalchemy import update

            await session.execute(
                update(NotificationOutbox)
                .where(
                    NotificationOutbox.user_id == user.id,
                    NotificationOutbox.template == "access_ready",
                    NotificationOutbox.status == NotificationOutboxStatus.PENDING.value,
                )
                .values(status=NotificationOutboxStatus.SENT.value, sent_at=datetime.utcnow())
            )
            await session.commit()
    except Exception:
        log.exception("immediate notify failed payment_id=%s", payment_id)

    await session.refresh(sub)
    return sub


async def process_outbox(session: AsyncSession, limit: int = 50) -> int:
    rows = list(
        await session.scalars(
            select(NotificationOutbox)
            .where(NotificationOutbox.status == NotificationOutboxStatus.PENDING.value)
            .order_by(NotificationOutbox.scheduled_at)
            .limit(limit)
        )
    )
    if not rows:
        return 0
    dispatcher = NotificationDispatcher()
    sent = 0
    for row in rows:
        user = await session.get(User, row.user_id)
        if not user:
            row.status = NotificationOutboxStatus.FAILED.value
            continue
        channel = NotificationChannel(row.channel)
        recipient = str(user.tg_id) if channel == NotificationChannel.TELEGRAM and user.tg_id else user.email
        payload = row.payload or {}
        body = payload.get("text") or f"NinaVPN: {row.template}"
        if row.template == "access_ready":
            body = (
                f"✅ NinaVPN готов!\n"
                f"Ссылка: {payload.get('subscription_url')}\n"
                f"До: {payload.get('expires_at') or '—'}"
            )
        elif row.template == "expiry_reminder":
            body = f"⏰ Подписка NinaVPN заканчивается: {payload.get('expires_at') or 'скоро'}"

        ok = await dispatcher.dispatch(
            NotificationMessage(
                channel=channel,
                template=row.template,
                recipient=recipient,
                subject=f"NinaVPN — {row.template}",
                body=body,
                payload=payload,
            )
        )
        if ok:
            row.status = NotificationOutboxStatus.SENT.value
            row.sent_at = datetime.utcnow()
            sent += 1
        else:
            row.status = NotificationOutboxStatus.FAILED.value
    await session.commit()
    return sent
