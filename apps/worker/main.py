"""ARQ worker: provision payments, flush notification outbox, expiry reminders."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import and_, select

from core.domain.enums import (
    NotificationChannel,
    NotificationOutboxStatus,
    ProvisionJobStatus,
    SubscriptionStatus,
)
from core.services.provision import process_outbox, run_provision_for_payment
from core.settings import saas_settings
from infrastructure.db.base import SaasSessionLocal
from infrastructure.db.models import NotificationOutbox, ProvisionJob, Subscription, User

log = logging.getLogger(__name__)


async def provision_payment(ctx, payment_id: int) -> str:
    async with SaasSessionLocal() as session:
        sub = await run_provision_for_payment(session, payment_id)
        return str(sub.id)


async def poll_queued_jobs(ctx) -> int:
    async with SaasSessionLocal() as session:
        jobs = list(
            await session.scalars(
                select(ProvisionJob)
                .where(ProvisionJob.status == ProvisionJobStatus.QUEUED.value)
                .order_by(ProvisionJob.created_at)
                .limit(20)
            )
        )
        done = 0
        for job in jobs:
            try:
                await run_provision_for_payment(session, job.payment_id)
                done += 1
            except Exception:
                log.exception("provision poll failed payment_id=%s", job.payment_id)
        return done


async def flush_outbox(ctx) -> int:
    async with SaasSessionLocal() as session:
        return await process_outbox(session)


async def expiry_reminders(ctx) -> int:
    """Queue reminders for subscriptions expiring within REMIND window."""
    try:
        from config import settings as bot_settings

        days = int(getattr(bot_settings, "REMIND_DAYS_BEFORE", 3) or 3)
    except Exception:
        days = 3

    now = datetime.utcnow()
    until = now + timedelta(days=days)
    created = 0
    async with SaasSessionLocal() as session:
        rows = list(
            await session.scalars(
                select(Subscription).where(
                    and_(
                        Subscription.status == SubscriptionStatus.ACTIVE.value,
                        Subscription.expires_at.is_not(None),
                        Subscription.expires_at <= until,
                        Subscription.expires_at > now,
                        Subscription.reminded_at.is_(None),
                    )
                ).limit(100)
            )
        )
        for sub in rows:
            user = await session.get(User, sub.user_id)
            if not user:
                continue
            channel = NotificationChannel.TELEGRAM if user.tg_id else NotificationChannel.EMAIL
            session.add(
                NotificationOutbox(
                    user_id=user.id,
                    channel=channel.value,
                    template="expiry_reminder",
                    payload={"expires_at": sub.expires_at.isoformat() if sub.expires_at else None},
                    status=NotificationOutboxStatus.PENDING.value,
                )
            )
            sub.reminded_at = now
            created += 1
        await session.commit()
    return created


async def startup(ctx):
    logging.basicConfig(level=logging.INFO)
    log.info("NinaVPN worker started")


class WorkerSettings:
    functions = [provision_payment, poll_queued_jobs, flush_outbox, expiry_reminders]
    cron_jobs = [
        cron(poll_queued_jobs, second={0, 30}),
        cron(flush_outbox, second={15, 45}),
        cron(expiry_reminders, minute={0, 30}),
    ]
    redis_settings = RedisSettings.from_dsn(saas_settings.REDIS_URL)
    on_startup = startup


def main():
    import sys

    from arq.cli import cli

    # `python -m apps.worker.main` → run worker with this settings module
    sys.argv = ["arq", "apps.worker.main.WorkerSettings"]
    cli()


if __name__ == "__main__":
    main()
