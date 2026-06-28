"""hash_api_keys_and_add_user_roles

Revision ID: 98464d906f8f
Revises: 0caed23d30a5
Create Date: 2026-06-27 19:54:04.926814

"""

import hashlib
import json
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "98464d906f8f"
down_revision: Union[str, Sequence[str], None] = "0caed23d30a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create api_user_roles table
    op.create_table(
        "api_user_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_user_roles_guild_id", "api_user_roles", ["guild_id"], unique=True)

    # 2. Add columns as nullable
    op.add_column("api_keys", sa.Column("key_hash", sa.String(length=255), nullable=True))
    op.add_column("api_keys", sa.Column("key_type", sa.String(length=50), nullable=True))
    op.add_column("api_keys", sa.Column("guild_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "api_keys", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True)
    )

    # 3. Perform data migration
    bind = op.get_bind()
    metadata = sa.MetaData()
    api_keys_table = sa.Table(
        "api_keys",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String),
        sa.Column("name", sa.String),
        sa.Column("key_hash", sa.String),
        sa.Column("key_type", sa.String),
        sa.Column("scopes", sa.String),
    )

    scope_map = {
        "global": "global.admin",
        "midi_library": "global.midi_library.user",
        "honeypot": "global.honeypot.admin",
        "utilities": "global.utilities.user",
    }

    results = bind.execute(
        sa.select(api_keys_table.c.id, api_keys_table.c.key, api_keys_table.c.name, api_keys_table.c.scopes)
    ).fetchall()
    for row in results:
        key_id, key, name, scopes_str = row
        if name == "system_internal":
            new_key_hash = key
            new_type = "internal"
            new_scopes = ["global.admin"]
        else:
            new_key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
            new_type = "global"
            try:
                old_scopes = json.loads(scopes_str)
                if not isinstance(old_scopes, list):
                    old_scopes = [old_scopes]
            except Exception:
                old_scopes = []
            new_scopes = [scope_map.get(s, s) for s in old_scopes]

        bind.execute(
            api_keys_table.update()
            .where(api_keys_table.c.id == key_id)
            .values(key_hash=new_key_hash, key_type=new_type, scopes=json.dumps(new_scopes))
        )

    # 4. Alter column key_hash, key_type, created_at to be non-nullable and add indexes
    op.alter_column("api_keys", "key_hash", nullable=False)
    op.alter_column("api_keys", "key_type", nullable=False)
    op.alter_column("api_keys", "created_at", nullable=False)
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    op.create_index("ix_api_keys_guild_id", "api_keys", ["guild_id"], unique=False)

    # 5. Drop index ix_api_keys_key and drop column key
    op.drop_index("ix_api_keys_key", table_name="api_keys")
    op.drop_column("api_keys", "key")


def downgrade() -> None:
    # 1. Add column key (nullable=True)
    op.add_column("api_keys", sa.Column("key", sa.String(length=255), nullable=True))

    # 2. Perform data migration (reverse)
    bind = op.get_bind()
    metadata = sa.MetaData()
    api_keys_table = sa.Table(
        "api_keys",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String),
        sa.Column("name", sa.String),
        sa.Column("key_hash", sa.String),
        sa.Column("scopes", sa.String),
    )

    reverse_scope_map = {
        "global.admin": "global",
        "global.midi_library.user": "midi_library",
        "global.honeypot.admin": "honeypot",
        "global.utilities.user": "utilities",
    }

    results = bind.execute(
        sa.select(api_keys_table.c.id, api_keys_table.c.key_hash, api_keys_table.c.name, api_keys_table.c.scopes)
    ).fetchall()
    for row in results:
        key_id, key_hash, name, scopes_str = row
        if name == "system_internal":
            new_key = key_hash
            new_scopes = ["global"]
        else:
            new_key = f"recovered_{key_hash[:20]}"
            try:
                old_scopes = json.loads(scopes_str)
                if not isinstance(old_scopes, list):
                    old_scopes = [old_scopes]
            except Exception:
                old_scopes = []
            new_scopes = [reverse_scope_map.get(s, s) for s in old_scopes]

        bind.execute(
            api_keys_table.update()
            .where(api_keys_table.c.id == key_id)
            .values(key=new_key, scopes=json.dumps(new_scopes))
        )

    # 3. Alter column key to be non-nullable and recreate index ix_api_keys_key
    op.alter_column("api_keys", "key", nullable=False)
    op.create_index("ix_api_keys_key", "api_keys", ["key"], unique=True)

    # 4. Drop indexes and columns
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_index("ix_api_keys_guild_id", table_name="api_keys")
    op.drop_column("api_keys", "key_hash")
    op.drop_column("api_keys", "key_type")
    op.drop_column("api_keys", "guild_id")
    op.drop_column("api_keys", "created_at")

    # 5. Drop table api_user_roles
    op.drop_table("api_user_roles")
