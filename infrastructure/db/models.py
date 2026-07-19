from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from core.domain.enums import (
    NotificationChannel,
    NotificationOutboxStatus,
    PaymentStatus,
    ProvisionJobStatus,
    SubscriptionStatus,
    SupportTicketStatus,
    UserRole,
)
from infrastructure.db.base import Base

# SQLite-friendly JSON fallback when not on Postgres
JsonType = JSON().with_variant(JSONB(), "postgresql")


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "saas_users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    # Stable numeric key for 3x-ui / Marzban client identity
    panel_user_key: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), default=UserRole.USER.value, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    referrer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_users.id"), nullable=True
    )
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


class RefreshToken(Base):
    __tablename__ = "saas_refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    device_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class Plan(Base):
    __tablename__ = "saas_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    plan_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    months: Mapped[int] = mapped_column(Integer, default=1)
    devices: Mapped[int] = mapped_column(Integer, default=1)
    price_rub: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Subscription(Base):
    __tablename__ = "saas_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_users.id"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_plans.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=SubscriptionStatus.PROVISIONING.value, nullable=False
    )
    devices: Mapped[int] = mapped_column(Integer, default=1)
    months: Mapped[int] = mapped_column(Integer, default=1)
    panel_client_email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    panel_uuid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    config_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_link_extra: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_qr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reminded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="subscriptions")
    plan: Mapped[Plan] = relationship()


class Payment(Base):
    __tablename__ = "saas_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_users.id"), nullable=False, index=True
    )
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_subscriptions.id"), nullable=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_plans.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    status: Mapped[str] = mapped_column(String(32), default=PaymentStatus.PENDING.value)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    checkout_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JsonType, nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="payments")
    plan: Mapped[Plan] = relationship()


class ProvisionJob(Base):
    __tablename__ = "saas_provision_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    payment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("saas_payments.id"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default=ProvisionJobStatus.QUEUED.value, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SupportTicket(Base):
    __tablename__ = "saas_support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_users.id"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=SupportTicketStatus.OPEN.value, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    messages: Mapped[list["SupportMessage"]] = relationship(back_populates="ticket")


class SupportMessage(Base):
    __tablename__ = "saas_support_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_support_tickets.id"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ticket: Mapped[SupportTicket] = relationship(back_populates="messages")


class NotificationOutbox(Base):
    __tablename__ = "saas_notification_outbox"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_users.id"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(
        String(32), default=NotificationChannel.TELEGRAM.value, nullable=False
    )
    template: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JsonType, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=NotificationOutboxStatus.PENDING.value, nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "saas_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromoCode(Base):
    __tablename__ = "saas_promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    bonus_days: Mapped[int] = mapped_column(Integer, default=0)
    max_uses: Mapped[int] = mapped_column(Integer, default=100)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class PromoRedemption(Base):
    __tablename__ = "saas_promo_redemptions"
    __table_args__ = (UniqueConstraint("promo_id", "user_id", name="uq_saas_promo_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promo_id: Mapped[int] = mapped_column(Integer, ForeignKey("saas_promo_codes.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saas_users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
