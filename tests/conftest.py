# ruff: noqa: E402
import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path FIRST — this must happen before any
# ``from app.*`` imports so that the ``app`` package is discoverable.
sys.path.append(str(Path(__file__).parent.parent))

# ──────────────────────────────────────────────────────────────────────────────
# TEST DATABASE ISOLATION
# ──────────────────────────────────────────────────────────────────────────────
# Tests MUST never touch the dev database (which may contain imported
# production data).  We FORCE ``POWERCORD_POSTGRES_DB`` to a dedicated
# test database name *before* any application module has a chance to read
# the value.  This overrides whatever ``.env`` provides via dotenv-load.
#
# The ``_create_test_db`` fixture below auto-creates the database on first
# run so there is zero manual setup required.
# ──────────────────────────────────────────────────────────────────────────────

# Provide required environment variables for tests before modules are imported.
# This prevents ValueError crashes when blueprints or widgets try to
# initialize DB connections at the module level.
os.environ.setdefault("POWERCORD_DB_HOST", "localhost:5433")
os.environ.setdefault("POWERCORD_POSTGRES_USER", "powercord")
os.environ.setdefault("POWERCORD_POSTGRES_PASSWORD", "test_pass")
os.environ.setdefault("POWERCORD_DISCORD_TOKEN", "dummy_token")
os.environ.setdefault("POWERCORD_SESSION_KEY", "dummy_session")

# FORCE the test database name — this is NOT a setdefault.  Even when the
# Justfile loads .env (which sets POWERCORD_POSTGRES_DB=powercord), tests
# must connect to the isolated test database.
from app.common.testing import TEST_DB_NAME

os.environ["POWERCORD_POSTGRES_DB"] = TEST_DB_NAME

import pytest
import sqlalchemy
from sqlmodel import Session, SQLModel, create_engine

# Construct a PostgreSQL URL using the *forced* test database name.
# The ``just test`` recipe ensures a PostgreSQL 15 container is running
# via the ``_ensure-db`` dependency.
_db_host = os.environ["POWERCORD_DB_HOST"]
_host_parts = _db_host.split(":")
DATABASE_URL = sqlalchemy.engine.URL.create(
    drivername="postgresql+pg8000",
    username=os.environ["POWERCORD_POSTGRES_USER"],
    password=os.environ["POWERCORD_POSTGRES_PASSWORD"],
    host=_host_parts[0],
    port=int(_host_parts[1]),
    database=TEST_DB_NAME,
)

from sqlalchemy.pool import NullPool

_test_engine = create_engine(DATABASE_URL, poolclass=NullPool)

import app.common.alchemy

original_init = app.common.alchemy.init_connection_engine


def mocked_init():
    import inspect

    for frame_info in inspect.stack():
        if "test_alchemy" in frame_info.filename:
            return original_init()
    app.common.alchemy._engine = _test_engine
    return _test_engine


app.common.alchemy.init_connection_engine = mocked_init
app.common.alchemy._engine = _test_engine


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default event loop to be session-scoped."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def _create_test_db():
    """Auto-create the isolated test database and enable pg_trgm.

    Runs once per test session before any other fixtures.  The database
    persists across sessions (it lives in the Docker volume) so subsequent
    runs are near-instant.
    """
    from app.common.testing import ensure_test_database

    ensure_test_database()


@pytest.fixture(name="engine", scope="session")
def fixture_engine(_create_test_db):
    """Provide a SQLAlchemy engine pointed at the isolated test database.

    Drops and recreates all tables at the start of the test session so that
    stale data from prior runs never bleeds into assertions.  The test DB is
    fully disposable — this is safe.
    """
    engine = _test_engine
    # Import all model classes to ensure SQLModel registers them before create_all
    from app.db.models import (  # noqa: F401
        AdminUser,
        ApiAccessRole,
        ApiKey,
        CustomContentItem,
        DashboardAccessRole,
        DiscordAuditorConfig,
        DiscordChannel,
        DiscordRole,
        GuildExtensionSettings,
        SiteSetting,
        UserSetting,
        WidgetSettings,
    )

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()
    try:
        from app.common.alchemy import _engine

        if _engine is not None:
            _engine.dispose()
    except ImportError:
        pass


@pytest.fixture(name="session")
def fixture_session(engine):
    """Provide a database session scoped to a single test."""
    with Session(engine) as session:
        yield session
        try:
            session.rollback()
            from sqlalchemy import text

            for table in SQLModel.metadata.tables.values():
                try:
                    session.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))
                    session.commit()
                except Exception:
                    session.rollback()
        except Exception:
            session.rollback()


@pytest.fixture(autouse=True)
def clear_global_caches():
    # Clear rule engine cache
    try:
        from app.extensions.utilities.widget import SecurityRuleEngine

        SecurityRuleEngine._evaluation_cache.clear()
    except ImportError:
        pass
    # Clear admin guilds helper cache
    try:
        from app.ui.helpers import _admin_guilds_cache

        _admin_guilds_cache.clear()
    except ImportError:
        pass
    # Stop background backup scheduler
    try:
        from app.db.db_tools import BackupService

        BackupService.stop_scheduler()
    except ImportError:
        pass


@pytest.fixture
def enable_honeypot(session):
    """Fixture to enable the honeypot extension in GuildExtensionSettings for tests.

    This prevents the Suggestive Honeypot Integration security rule (Rule 7)
    from triggering a default configuration alert.
    """
    from app.db.models import GuildExtensionSettings

    honeypot_setting = GuildExtensionSettings(
        guild_id=999123,
        extension_name="honeypot",
        gadget_type="cog",
        is_enabled=True,
    )
    session.add(honeypot_setting)
    session.commit()
    return honeypot_setting
