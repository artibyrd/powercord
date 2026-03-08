from unittest.mock import MagicMock, patch

import pytest

from app.db.models import GuildExtensionSettings
from app.ui.helpers import update_guild_extension_setting

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


@patch("app.ui.helpers.init_connection_engine")
@patch("app.ui.helpers.Session")
def test_update_guild_extension_setting_new_record(mock_session_cls, mock_init_engine):
    """Test creating a new record when one doesn't exist."""
    guild_id = 123
    extension_name = "test_ext"
    gadget_type = "cog"
    is_enabled = True

    # Mock DB session and query results
    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session
    mock_session.exec.return_value.first.return_value = None  # No existing record

    update_guild_extension_setting(guild_id, extension_name, gadget_type, is_enabled)

    # Verify a new record was added
    mock_session.add.assert_called_once()
    args, _ = mock_session.add.call_args
    new_record = args[0]
    assert isinstance(new_record, GuildExtensionSettings)
    assert new_record.guild_id == guild_id
    assert new_record.extension_name == extension_name
    assert new_record.gadget_type == gadget_type
    assert new_record.is_enabled == is_enabled
    mock_session.commit.assert_called_once()


@patch("app.ui.helpers.init_connection_engine")
@patch("app.ui.helpers.Session")
def test_update_guild_extension_setting_update_existing(mock_session_cls, mock_init_engine):
    """Test updating an existing record."""
    guild_id = 123
    extension_name = "test_ext"
    gadget_type = "cog"
    is_enabled = False

    # Mock DB session and query results
    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session

    # Mock existing record
    existing_record = GuildExtensionSettings(
        guild_id=guild_id, extension_name=extension_name, gadget_type=gadget_type, is_enabled=True
    )
    mock_session.exec.return_value.first.return_value = existing_record

    update_guild_extension_setting(guild_id, extension_name, gadget_type, is_enabled)

    # Verify record was updated
    mock_session.add.assert_called_once_with(existing_record)
    assert existing_record.is_enabled == is_enabled
    mock_session.commit.assert_called_once()
