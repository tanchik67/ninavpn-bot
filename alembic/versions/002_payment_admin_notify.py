"""payments: admin_notify_sent для Сбер-оплаты

Revision ID: 002_admin_notify
Revises: 001_initial
Create Date: 2026-04-05

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002_admin_notify"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column(
            "admin_notify_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("payments", "admin_notify_sent")
