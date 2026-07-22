"""saas oauth fields: nullable password_hash, google_sub

Revision ID: 002_saas_oauth
Revises: 001_saas
Create Date: 2026-07-21
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_saas_oauth"
down_revision: Union[str, None] = "001_saas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "saas_users",
        "password_hash",
        existing_type=sa.String(255),
        nullable=True,
    )
    op.add_column(
        "saas_users",
        sa.Column("google_sub", sa.String(128), nullable=True),
    )
    op.create_index("ix_saas_users_google_sub", "saas_users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_saas_users_google_sub", table_name="saas_users")
    op.drop_column("saas_users", "google_sub")
    op.alter_column(
        "saas_users",
        "password_hash",
        existing_type=sa.String(255),
        nullable=False,
    )
