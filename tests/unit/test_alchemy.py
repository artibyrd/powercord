import os
from unittest.mock import patch

import pytest

from app.common.alchemy import get_database_url

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


def test_get_database_url_success():
    """Test get_database_url with valid environment variables."""
    with patch.dict(
        os.environ,
        {
            "POWERCORD_POSTGRES_USER": "test_user",
            "POWERCORD_POSTGRES_PASSWORD": "test_password",
            "POWERCORD_POSTGRES_DB": "test_db",
            "POWERCORD_DB_HOST": "localhost:5432",
        },
    ):
        url = get_database_url()
        assert url.username == "test_user"
        assert url.password == "test_password"
        assert url.host == "localhost"
        assert url.port == 5432
        assert url.database == "test_db"
        assert url.drivername == "postgresql+pg8000"


def test_get_database_url_missing_host():
    """Test get_database_url when POWERCORD_DB_HOST is missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="POWERCORD_DB_HOST environment variable is missing or empty"):
            get_database_url()


def test_get_database_url_invalid_format():
    """Test get_database_url with invalid POWERCORD_DB_HOST format."""
    with patch.dict(os.environ, {"POWERCORD_DB_HOST": "invalid_format"}):
        with pytest.raises(ValueError, match="Invalid POWERCORD_DB_HOST format"):
            get_database_url()


@patch("app.common.alchemy.init_tcp_connection_engine")
def test_init_connection_engine(mock_tcp):
    """Test that init_connection_engine passes the correct dict to init_tcp_connection_engine."""
    import app.common.alchemy as alchemy_module
    from app.common.alchemy import init_connection_engine

    # Reset the singleton so init_tcp_connection_engine is invoked fresh
    original_engine = alchemy_module._engine
    alchemy_module._engine = None
    try:
        init_connection_engine()
        mock_tcp.assert_called_once()
        args, kwargs = mock_tcp.call_args
        assert args[0]["pool_size"] == 5
        assert args[0]["max_overflow"] == 2

        # Calling again should reuse the cached engine (no second call)
        init_connection_engine()
        mock_tcp.assert_called_once()  # still only one call
    finally:
        # Restore original state to avoid polluting other tests
        alchemy_module._engine = original_engine


@patch("app.common.alchemy.get_database_url")
@patch("app.common.alchemy.create_engine")
def test_init_tcp_connection_engine(mock_create_engine, mock_get_db_url):
    """Test that init_tcp_connection_engine creates an engine with the url."""
    from app.common.alchemy import init_tcp_connection_engine

    mock_get_db_url.return_value = "mock_url"
    mock_create_engine.return_value = "mock_engine"

    engine = init_tcp_connection_engine({"pool_size": 1})

    mock_get_db_url.assert_called_once()
    mock_create_engine.assert_called_once_with("mock_url", pool_size=1)
    assert engine == "mock_engine"


@patch("app.common.alchemy.init_connection_engine")
@patch("app.common.alchemy.Session")
def test_get_session(mock_session_cls, mock_init_engine):
    """
    Test the FastAPI Dependency Generator for Database Sessions.

    Verifies that calling get_session():
    1. Initializes the connection engine (if not already done).
    2. Yields a valid SQLModel Session block tied to that engine.
    """
    from app.common.alchemy import get_session

    mock_init_engine.return_value = "mock_engine"

    # Mock the context manager __enter__ return value for the Session block
    mock_session_cls.return_value.__enter__.return_value = "fake_session"

    generator = get_session()

    # Grab the first yield from the generator
    session = next(generator)

    assert session == "fake_session"
    mock_init_engine.assert_called_once()
