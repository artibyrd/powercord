"""refactor_settings

Revision ID: f9e3c8d1e7b6
Revises: 85c3de0b173c
Create Date: 2026-06-16 06:22:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9e3c8d1e7b6"
down_revision: Union[str, Sequence[str], None] = "85c3de0b173c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Drop show_sidebar column from user_settings table
    op.drop_column("user_settings", "show_sidebar")

    # 2. Add position_config column to widget_settings table
    op.add_column("widget_settings", sa.Column("position_config", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop position_config column from widget_settings table
    op.drop_column("widget_settings", "position_config")

    # 2. Add show_sidebar column back to user_settings table
    op.add_column(
        "user_settings", sa.Column("show_sidebar", sa.Boolean(), server_default=sa.text("true"), nullable=False)
    )
