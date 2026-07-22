"""saas profile emoji on users

Revision ID: 003_profile_emoji
Revises: 002_saas_oauth
Create Date: 2026-07-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_profile_emoji"
down_revision: Union[str, None] = "002_saas_oauth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "saas_users",
        sa.Column("profile_emoji", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("saas_users", "profile_emoji")
