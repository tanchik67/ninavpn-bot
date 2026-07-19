"""saas initial schema

Revision ID: 001_saas
Revises:
Create Date: 2026-07-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_saas"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saas_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("tg_id", sa.BigInteger(), nullable=True),
        sa.Column("panel_user_key", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("referrer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_users.id"), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_saas_users_email", "saas_users", ["email"], unique=True)
    op.create_index("ix_saas_users_tg_id", "saas_users", ["tg_id"], unique=True)
    op.create_index("ix_saas_users_panel_user_key", "saas_users", ["panel_user_key"], unique=True)

    op.create_table(
        "saas_refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_users.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_saas_refresh_tokens_user_id", "saas_refresh_tokens", ["user_id"])

    op.create_table(
        "saas_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("months", sa.Integer(), nullable=False),
        sa.Column("devices", sa.Integer(), nullable=False),
        sa.Column("price_rub", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_saas_plans_plan_key", "saas_plans", ["plan_key"], unique=True)

    op.create_table(
        "saas_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_users.id"), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_plans.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("devices", sa.Integer(), nullable=False),
        sa.Column("months", sa.Integer(), nullable=False),
        sa.Column("panel_client_email", sa.String(128), nullable=True),
        sa.Column("panel_uuid", sa.String(64), nullable=True),
        sa.Column("config_link", sa.Text(), nullable=True),
        sa.Column("config_link_extra", sa.Text(), nullable=True),
        sa.Column("config_qr", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("reminded_at", sa.DateTime(), nullable=True),
        sa.Column("disabled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_saas_subscriptions_user_id", "saas_subscriptions", ["user_id"])

    op.create_table(
        "saas_payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_users.id"), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_subscriptions.id"), nullable=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_plans.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_payment_id", sa.String(128), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("checkout_token", sa.String(64), nullable=True, unique=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_saas_payments_user_id", "saas_payments", ["user_id"])
    op.create_index("ix_saas_payments_provider_payment_id", "saas_payments", ["provider_payment_id"])

    op.create_table(
        "saas_provision_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("saas_payments.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "saas_support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_users.id"), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_saas_support_tickets_user_id", "saas_support_tickets", ["user_id"])

    op.create_table(
        "saas_support_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_support_tickets.id"), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "saas_notification_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_users.id"), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("template", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "saas_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_users.id"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_saas_audit_logs_action", "saas_audit_logs", ["action"])

    op.create_table(
        "saas_promo_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("bonus_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "saas_promo_redemptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("promo_id", sa.Integer(), sa.ForeignKey("saas_promo_codes.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("promo_id", "user_id", name="uq_saas_promo_user"),
    )


def downgrade() -> None:
    for table in (
        "saas_promo_redemptions",
        "saas_promo_codes",
        "saas_audit_logs",
        "saas_notification_outbox",
        "saas_support_messages",
        "saas_support_tickets",
        "saas_provision_jobs",
        "saas_payments",
        "saas_subscriptions",
        "saas_plans",
        "saas_refresh_tokens",
        "saas_users",
    ):
        op.drop_table(table)
