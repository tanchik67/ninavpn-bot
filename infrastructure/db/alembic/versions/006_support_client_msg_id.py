"""support message client_msg_id for idempotent send

Revision ID: 006_support_client_msg_id
Revises: 005_support_image
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_support_client_msg_id"
down_revision: Union[str, None] = "005_support_image"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "saas_support_messages",
        sa.Column("client_msg_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_saas_support_messages_ticket_client_msg",
        "saas_support_messages",
        ["ticket_id", "client_msg_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_saas_support_messages_ticket_client_msg",
        table_name="saas_support_messages",
    )
    op.drop_column("saas_support_messages", "client_msg_id")
