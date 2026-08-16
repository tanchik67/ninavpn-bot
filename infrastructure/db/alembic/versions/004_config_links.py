"""Add saas_subscriptions.config_links JSON array

Revision ID: 004_config_links
Revises: 003_profile_emoji
Create Date: 2026-07-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_config_links"
down_revision: Union[str, None] = "003_profile_emoji"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        col = sa.Column("config_links", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    else:
        col = sa.Column("config_links", sa.JSON(), nullable=True)
    op.add_column("saas_subscriptions", col)


def downgrade() -> None:
    op.drop_column("saas_subscriptions", "config_links")
