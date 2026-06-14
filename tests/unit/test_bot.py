from unittest.mock import MagicMock, patch

import pytest

from app.main_bot import get_prefix

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


# Test get_prefix
def test_get_prefix_no_guild():
    bot = MagicMock()
    message = MagicMock()
    message.guild = None
    assert get_prefix(bot, message) == 0


def test_get_prefix_with_guild():
    bot = MagicMock()
    message = MagicMock()
    message.guild = "test_guild"
    message.content = "$test"

    # Mocking when_mentioned_or since it returns a callable
    with patch("nextcord.ext.commands.when_mentioned_or") as mock_when_mentioned_or:
        mock_callable = MagicMock()
        mock_when_mentioned_or.return_value = mock_callable

        get_prefix(bot, message)

        mock_when_mentioned_or.assert_called_with("$", "Powercord", "Powerbot")
        mock_callable.assert_called_with(bot, message)


@patch("app.common.alchemy.init_connection_engine")
@patch("sqlmodel.Session")
def test_get_enabled_guild_ids_globally_disabled(mock_session_cls, mock_init_engine):
    from app.db.models import GuildExtensionSettings
    from app.main_bot import get_enabled_guild_ids

    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session

    # Global setting explicitly disabled
    global_setting = GuildExtensionSettings(guild_id=0, extension_name="test_ext", gadget_type="cog", is_enabled=False)
    mock_session.exec.return_value.first.return_value = global_setting

    bot = MagicMock()
    bot.guilds = [MagicMock(id=123), MagicMock(id=456)]

    enabled = get_enabled_guild_ids(bot, "test_ext")
    assert enabled == set()


@patch("app.common.alchemy.init_connection_engine")
@patch("sqlmodel.Session")
def test_get_enabled_guild_ids_globally_enabled_no_local_overrides(mock_session_cls, mock_init_engine):
    from app.db.models import GuildExtensionSettings
    from app.main_bot import get_enabled_guild_ids

    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session

    # Global setting enabled
    global_setting = GuildExtensionSettings(guild_id=0, extension_name="test_ext", gadget_type="cog", is_enabled=True)
    mock_session.exec.return_value.first.return_value = global_setting
    # Local settings: none (empty list)
    mock_session.exec.return_value.all.return_value = []

    bot = MagicMock()
    g1 = MagicMock()
    g1.id = 123
    g2 = MagicMock()
    g2.id = 456
    bot.guilds = [g1, g2]

    enabled = get_enabled_guild_ids(bot, "test_ext")
    assert enabled == {123, 456}


@patch("app.common.alchemy.init_connection_engine")
@patch("sqlmodel.Session")
def test_get_enabled_guild_ids_with_local_override(mock_session_cls, mock_init_engine):
    from app.db.models import GuildExtensionSettings
    from app.main_bot import get_enabled_guild_ids

    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session

    # Global setting enabled
    global_setting = GuildExtensionSettings(guild_id=0, extension_name="test_ext", gadget_type="cog", is_enabled=True)
    mock_session.exec.return_value.first.return_value = global_setting
    # Local settings: guild 456 disabled
    local_settings = [
        GuildExtensionSettings(guild_id=456, extension_name="test_ext", gadget_type="cog", is_enabled=False)
    ]
    mock_session.exec.return_value.all.return_value = local_settings

    bot = MagicMock()
    g1 = MagicMock()
    g1.id = 123
    g2 = MagicMock()
    g2.id = 456
    bot.guilds = [g1, g2]

    enabled = get_enabled_guild_ids(bot, "test_ext")
    assert enabled == {123}


@patch("app.main_bot.get_enabled_guild_ids")
def test_update_command_routing(mock_get_enabled):
    from app.main_bot import Bot

    # Create dummy bot with mocked attributes
    bot = MagicMock(spec=Bot)
    bot._connection = MagicMock()
    bot._connection._application_commands = set()
    bot._connection._application_command_ids = {}
    bot._connection._application_command_signatures = {}

    # Define a core/global command
    cmd_global = MagicMock()
    cmd_global.cog = None
    cmd_global.command_ids = {None: 1}
    cmd_global.guild_ids_to_rollout = set()

    # Define an extension command
    cmd_ext = MagicMock()
    cog_ext = MagicMock()
    cog_ext.__module__ = "app.extensions.utilities.cog"
    cmd_ext.cog = cog_ext
    cmd_ext.command_ids = {None: 2}
    cmd_ext.guild_ids_to_rollout = set()

    # Populate bot's all_loaded_commands
    bot._all_loaded_commands = {cmd_global, cmd_ext}
    bot._connection._application_commands = bot._all_loaded_commands.copy()

    # Mock enabled guilds for utilities extension
    mock_get_enabled.return_value = {123}

    # Call the method
    with patch("app.main_bot._strict_guild_ids", []):
        Bot._update_command_routing(bot)

    # Assertions:
    # 1. cmd_global should remain global
    assert cmd_global.force_global is True
    assert cmd_global.guild_ids_to_rollout == set()
    assert None in cmd_global.command_ids

    # 2. cmd_ext should be routed to guild 123 and popped global
    assert cmd_ext.force_global is False
    assert cmd_ext.guild_ids_to_rollout == {123}
    assert None not in cmd_ext.command_ids

    # 3. bot.add_application_command should have been called for both
    # with use_rollout=True and pre_remove=False
    bot.add_application_command.assert_any_call(cmd_global, use_rollout=True, pre_remove=False)
    bot.add_application_command.assert_any_call(cmd_ext, use_rollout=True, pre_remove=False)
