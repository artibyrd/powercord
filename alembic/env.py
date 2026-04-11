import importlib
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.common.alchemy import get_database_url
from app.db import models  # noqa: F401

# Dynamically import all installed extension blueprints so Alembic's
# autogenerate can detect their SQLModel tables.  Only extensions that
# are currently installed under app/extensions/ will be picked up.
# We also automatically mount any extension's isolated alembic/versions
# folder to facilitate localized decoupled schema migrations.
import os

_extensions_dir = Path(__file__).resolve().parents[1] / "app" / "extensions"
_version_locations = [str(Path(__file__).resolve().parent / "versions")]

for _ext_path in sorted(_extensions_dir.iterdir()):
    if _ext_path.is_dir():
        if (_ext_path / "blueprint.py").exists():
            importlib.import_module(f"app.extensions.{_ext_path.name}.blueprint")
        
        _ext_versions = _ext_path / "alembic" / "versions"
        if _ext_versions.exists():
            _version_locations.append(str(_ext_versions))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Inject dynamic version locations for proper extension migration discovery
config.set_main_option("version_locations", os.pathsep.join(_version_locations))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # url = config.get_main_option("sqlalchemy.url")
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section, {})
    # Override sqlalchemy.url with dynamic URL
    url = get_database_url()
    # The URL object from sqlalchemy needs to be converted to string for alembic config
    configuration["sqlalchemy.url"] = url.render_as_string(hide_password=False)

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
