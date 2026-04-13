import asyncio
import os
import sys
from pathlib import Path

# Provide required environment variables for tests before modules are imported.
# This prevents ValueError crashes when blueprints or widgets try to initialize DB connections at the module level.
os.environ.setdefault("POWERCORD_DB_HOST", "localhost:5433")
os.environ.setdefault("POWERCORD_POSTGRES_USER", "test_user")
os.environ.setdefault("POWERCORD_POSTGRES_PASSWORD", "test_pass")
os.environ.setdefault("POWERCORD_POSTGRES_DB", "test_db")
os.environ.setdefault("POWERCORD_DISCORD_TOKEN", "dummy_token")
os.environ.setdefault("POWERCORD_SESSION_KEY", "dummy_session")

import pytest

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Use an in-memory SQLite database for testing to avoid needing a running Postgres instance
# for basic logic tests, OR use a test-specific Postgres URL.
# For this setup, we'll try to use the environment variable if present, else fallback to sqlite.
DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default event loop to be session-scoped."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(name="engine", scope="session")
def fixture_engine():
    if DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(DATABASE_URL)

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def fixture_session(engine):
    with Session(engine) as session:
        yield session
