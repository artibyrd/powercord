"""add honeypot logging and shame mode

Revision ID: 6991c1eb9a2f
Revises: 4f239f105949
Create Date: 2026-03-02 14:16:53.475708

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6991c1eb9a2f"
down_revision: Union[str, Sequence[str], None] = "4f239f105949"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — only runs if the honeypot extension is installed."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "honeypot_settings" in inspector.get_table_names():
        op.add_column("honeypot_settings", sa.Column("log_channel_id", sa.BigInteger(), nullable=True))
        op.add_column(
            "honeypot_settings", sa.Column("shame_mode", sa.Boolean(), server_default="false", nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "honeypot_settings" in inspector.get_table_names():
        op.drop_column("honeypot_settings", "shame_mode")
        op.drop_column("honeypot_settings", "log_channel_id")
