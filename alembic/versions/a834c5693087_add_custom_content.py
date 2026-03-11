""" "add_custom_content"

Revision ID: a834c5693087
Revises: 1c7fc4ef8015
Create Date: 2026-03-10 21:53:24.014839

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a834c5693087"
down_revision: Union[str, Sequence[str], None] = "1c7fc4ef8015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "custom_content_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("format", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_custom_content_items_guild_id"), "custom_content_items", ["guild_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_custom_content_items_guild_id"), table_name="custom_content_items")
    op.drop_table("custom_content_items")
