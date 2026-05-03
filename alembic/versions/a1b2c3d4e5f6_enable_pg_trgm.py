"""enable_pg_trgm

Revision ID: a1b2c3d4e5f6
Revises: 4d30ec975899
Create Date: 2026-05-03 08:30:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "4d30ec975899"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable the pg_trgm extension for trigram-based fuzzy search."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    """Remove the pg_trgm extension."""
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
