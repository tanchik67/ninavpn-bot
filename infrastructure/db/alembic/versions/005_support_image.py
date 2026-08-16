"""support message image attachment

Revision ID: 005_support_image
Revises: 004_config_links
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_support_image"
down_revision: Union[str, None] = "004_config_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "saas_support_messages",
        sa.Column("image_path", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("saas_support_messages", "image_path")
