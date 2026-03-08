"""add_grid_xy_to_widget_settings

Revision ID: 4f239f105949
Revises: f93f62c123e1
Create Date: 2026-02-16 01:04:03.119918

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f239f105949"
down_revision: Union[str, Sequence[str], None] = "f93f62c123e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("widget_settings", sa.Column("grid_x", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("widget_settings", sa.Column("grid_y", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("widget_settings", "grid_y")
    op.drop_column("widget_settings", "grid_x")
