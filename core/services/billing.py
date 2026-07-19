from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.payments.factory import get_payment_gateway
from core.domain.enums import PaymentStatus, ProvisionJobStatus
from core.services.audit import write_audit
from core.settings import saas_settings
from infrastructure.db.models import Payment, Plan, ProvisionJob, Subscription, User
from infrastructure.redis.client import get_redis


class BillingError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


async def list_active_plans(session: AsyncSession) -> list[Plan]:
    rows = await session.scalars(
        select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.sort_order, Plan.price_rub)
    )
    return list(rows)


async def seed_default_plans(session: AsyncSession) -> None:
    """Seed from bot PLANS if saas_plans empty."""
    count = await session.scalar(select(Plan.id).limit(1))
    if count:
        return
    try:
        from config import PLANS
    except Exception:
        PLANS = {
            "1m_1d": {"name": "Старт", "months": 1, "devices": 1, "price_rub": 100, "description": "1 мес · 1 устр."},
            "6m_3d": {"name": "Хит", "months": 6, "devices": 3, "price_rub": 500, "description": "6 мес · 3 устр."},
            "12m_5d": {"name": "Год", "months": 12, "devices": 5, "price_rub": 1000, "description": "12 мес · 5 устр."},
        }
    for i, (key, p) in enumerate(PLANS.items()):
        session.add(
            Plan(
                plan_key=key,
                name=p.get("name") or key,
                description=p.get("description"),
                months=int(p.get("months") or 1),
                devices=int(p.get("devices") or 1),
                price_rub=float(p.get("price_rub") or 0),
                is_active=True,
                sort_order=i,
            )
        )
    await session.commit()


async def get_plan_by_key(session: AsyncSession, plan_key: str) -> Optional[Plan]:
    return await session.scalar(select(Plan).where(Plan.plan_key == plan_key, Plan.is_active.is_(True)))


def _public_base() -> str:
    base = (saas_settings.SAAS_PUBLIC_BASE_URL or "http://localhost:8000").rstrip("/")
    return base


async def create_checkout(
    session: AsyncSession,
    *,
    user: User,
    plan_key: str,
    provider: Optional[str] = None,
    ip: Optional[str] = None,
) -> tuple[Payment, str]:
    plan = await get_plan_by_key(session, plan_key)
    if not plan:
        raise BillingError("plan_not_found", "Plan not found")

    gateway = get_payment_gateway(provider)
    idem = secrets.token_hex(16)
    payment = Payment(
        user_id=user.id,
        plan_id=plan.id,
        provider=gateway.name,
        amount=float(plan.price_rub),
        currency="RUB",
        status=PaymentStatus.PENDING.value,
        idempotency_key=idem,
        checkout_token=secrets.token_urlsafe(24),
    )
    session.add(payment)
    await session.flush()

    api_base = _public_base()
    success_url = f"{api_base}/api/v1/payments/return/success?token={payment.checkout_token}"
    fail_url = f"{api_base}/api/v1/payments/return/fail?token={payment.checkout_token}"
    notification_url = f"{api_base}/api/v1/payments/webhooks/{gateway.name}"

    result = await gateway.create_payment(
        payment_id=payment.id,
        amount_rub=payment.amount,
        description=f"NinaVPN {plan.name}",
        success_url=success_url,
        fail_url=fail_url,
        notification_url=notification_url,
        customer_email=user.email,
    )
    payment.provider_payment_id = result.provider_payment_id
    payment.raw_payload = result.raw
    payment.status = PaymentStatus.PROCESSING.value

    await write_audit(
        session,
        action="payment.checkout",
        entity_type="payment",
        entity_id=str(payment.id),
        actor_user_id=user.id,
        ip=ip,
        meta={"plan_key": plan_key, "provider": gateway.name},
    )
    await session.commit()
    await session.refresh(payment)
    return payment, result.payment_url


async def confirm_payment_and_enqueue(
    session: AsyncSession,
    *,
    payment_id: int,
    provider_payment_id: Optional[str] = None,
    raw: Optional[dict] = None,
    actor_user_id: Optional[UUID] = None,
) -> Payment:
    redis = await get_redis()
    lock_key = f"pay:confirm:{payment_id}"
    got = await redis.set(lock_key, "1", nx=True, ex=60)
    if not got:
        payment = await session.get(Payment, payment_id)
        if not payment:
            raise BillingError("payment_not_found")
        return payment

    try:
        payment = await session.get(Payment, payment_id)
        if not payment:
            raise BillingError("payment_not_found")
        if payment.status == PaymentStatus.CONFIRMED.value:
            # Idempotent re-entry: finish provision if still pending/failed
            try:
                from core.services.provision import run_provision_for_payment

                await run_provision_for_payment(session, payment.id)
            except Exception:
                pass
            return payment

        payment.status = PaymentStatus.CONFIRMED.value
        payment.confirmed_at = datetime.utcnow()
        if provider_payment_id:
            payment.provider_payment_id = provider_payment_id
        if raw is not None:
            payment.raw_payload = {**(payment.raw_payload or {}), "webhook": raw}

        existing_job = await session.scalar(
            select(ProvisionJob).where(ProvisionJob.payment_id == payment.id)
        )
        if not existing_job:
            session.add(
                ProvisionJob(
                    payment_id=payment.id,
                    status=ProvisionJobStatus.QUEUED.value,
                )
            )

        await write_audit(
            session,
            action="payment.confirmed",
            entity_type="payment",
            entity_id=str(payment.id),
            actor_user_id=actor_user_id,
            meta={"provider_payment_id": provider_payment_id},
        )
        await session.commit()
        await session.refresh(payment)

        # Prefer ARQ worker; always also try inline so MVP works without a running worker.
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            redis_settings = RedisSettings.from_dsn(saas_settings.REDIS_URL)
            pool = await create_pool(redis_settings)
            await pool.enqueue_job("provision_payment", payment.id)
            await pool.aclose()
        except Exception:
            pass

        try:
            from core.services.provision import run_provision_for_payment

            await run_provision_for_payment(session, payment.id)
        except Exception:
            # Job row keeps last_error / failed|queued for client polling
            pass

        return payment
    finally:
        await redis.delete(lock_key)


async def get_payment(session: AsyncSession, payment_id: int, user_id: UUID) -> Optional[Payment]:
    payment = await session.get(Payment, payment_id)
    if not payment or payment.user_id != user_id:
        return None
    return payment


async def payment_status_detail(session: AsyncSession, payment_id: int, user_id: UUID) -> Optional[dict]:
    payment = await get_payment(session, payment_id, user_id)
    if not payment:
        return None

    job = await session.scalar(select(ProvisionJob).where(ProvisionJob.payment_id == payment.id))
    sub = None
    if payment.subscription_id:
        sub = await session.get(Subscription, payment.subscription_id)
    if sub is None:
        # latest active for user after provision
        sub = await latest_subscription(session, user_id)

    has_config = bool(sub and (sub.config_link or sub.config_qr))
    prov_status = job.status if job else None
    ready = bool(
        payment.status == PaymentStatus.CONFIRMED.value
        and prov_status == ProvisionJobStatus.SUCCEEDED.value
        and has_config
    )
    return {
        "payment_id": payment.id,
        "payment_status": payment.status,
        "provider": payment.provider,
        "provision_status": prov_status,
        "provision_error": (job.last_error if job else None),
        "subscription_id": sub.id if sub else None,
        "subscription_status": sub.status if sub else None,
        "has_config": has_config,
        "ready": ready,
    }


async def latest_subscription(session: AsyncSession, user_id: UUID) -> Optional[Subscription]:
    return await session.scalar(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .options(selectinload(Subscription.plan))
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
