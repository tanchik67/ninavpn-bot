"""saas_users.referral_rewarded_at — invitee already granted referrer bonus

Revision ID: 007_referral_rewarded
Revises: 006_support_client_msg_id
Create Date: 2026-08-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_referral_rewarded"
down_revision: Union[str, None] = "006_support_client_msg_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "saas_users",
        sa.Column("referral_rewarded_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("saas_users", "referral_rewarded_at")
