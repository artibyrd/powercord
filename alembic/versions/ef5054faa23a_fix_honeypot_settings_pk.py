""" "fix_honeypot_settings_pk"

Revision ID: ef5054faa23a
Revises: 9a36ad5e5114
Create Date: 2026-03-07 14:05:36.391170

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ef5054faa23a"
down_revision: Union[str, Sequence[str], None] = "9a36ad5e5114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — only runs if the honeypot extension is installed."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "honeypot_settings" not in inspector.get_table_names():
        return

    # Check if the 'id' column already exists (idempotent)
    columns = [col["name"] for col in inspector.get_columns("honeypot_settings")]
    if "id" in columns:
        return

    # 1. Drop existing primary key on guild_id
    op.drop_constraint("honeypot_settings_pkey", "honeypot_settings", type_="primary")

    # 2. Add id column as a serial/autoincrement
    op.add_column(
        "honeypot_settings", sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, primary_key=True)
    )

    # 3. Create a new primary key constraint on 'id'
    op.create_primary_key("honeypot_settings_pkey", "honeypot_settings", ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "honeypot_settings" not in inspector.get_table_names():
        return

    # 1. Drop the primary key constraint on 'id'
    op.drop_constraint("honeypot_settings_pkey", "honeypot_settings", type_="primary")

    # 2. Drop the 'id' column
    op.drop_column("honeypot_settings", "id")

    # 3. Re-add the primary key constraint on 'guild_id'
    op.create_primary_key("honeypot_settings_pkey", "honeypot_settings", ["guild_id"])
