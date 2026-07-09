"""payments: checkout_token and checkout_email for site checkout

Revision ID: 003_checkout_token
Revises: 002_admin_notify
Create Date: 2026-07-09

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_checkout_token"
down_revision = "002_admin_notify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("checkout_token", sa.String(64), nullable=True))
    op.add_column("payments", sa.Column("checkout_email", sa.String(254), nullable=True))
    op.create_index("ix_payments_checkout_token", "payments", ["checkout_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_payments_checkout_token", table_name="payments")
    op.drop_column("payments", "checkout_email")
    op.drop_column("payments", "checkout_token")
