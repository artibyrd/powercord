from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot.powerloader import AppPowerLoader

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


@pytest.fixture
def mock_bot():
    """Provides a mocked bot instance with predefined cog states for testing."""
    bot = MagicMock()
    # Mock the internal cog report to simulate loaded cogs and their requirements
    bot.cog_report = {
        "all_cogs": ["cog1", "cog2"],
        "cog_custom_contexts": {"cog1": True},
        "cog_persistent_modals": {},
        "cog_persistent_views": {},
    }
    # Mock bot guilds to ensure application commands can be locally rolled out
    bot.guilds = [MagicMock(id=1), MagicMock(id=2)]
    bot.guilds[0].rollout_application_commands = AsyncMock()
    bot.guilds[1].rollout_application_commands = AsyncMock()
    bot.rollout_application_commands = AsyncMock()
    return bot


@pytest.fixture
def loader(mock_bot):
    """Provides an instance of AppPowerLoader initialized with the mock bot."""
    return AppPowerLoader(mock_bot)


def test_hotload_caution(loader):
    """Verifies that cogs requiring preloads are correctly identified for hotload caution."""
    # cog1 should trigger caution because it requires custom contexts
    assert loader._hotload_caution("cog1") is True
    # cog2 has no extra requirements, so it should be false
    assert loader._hotload_caution("cog2") is False


@pytest.mark.asyncio
async def test_extension_handler_caution(loader):
    """Ensures the extension handler blocks actions on cogs that trigger hotload caution."""
    msg = await loader._extension_handler("cog1")
    assert "cannot be hot loaded/unloaded/reloaded" in msg


@pytest.mark.asyncio
async def test_extension_handler_load(loader, mock_bot):
    """Tests the loading of a safe extension and verifies command rollout is triggered."""
    msg = await loader._extension_handler("cog2", load=True, unload=False)
    # Ensure the bot's load_extension method was called with the correct path
    mock_bot.load_extension.assert_called_once_with("app.extensions.cog2.cog")
    assert "**`cog2` loaded.**" in msg
    # Verify that commands were rolled out globally and to guilds
    mock_bot.rollout_application_commands.assert_called_once()
    mock_bot.guilds[0].rollout_application_commands.assert_called_once()


@pytest.mark.asyncio
async def test_extension_handler_unload(loader, mock_bot):
    """Tests the unloading of an extension."""
    msg = await loader._extension_handler("cog2", load=False, unload=True)
    mock_bot.unload_extension.assert_called_once_with("app.extensions.cog2.cog")
    assert "**`cog2` unloaded.**" in msg


@pytest.mark.asyncio
async def test_extension_handler_reload(loader, mock_bot):
    """Tests the reloading of an extension by verifying both unload and load are called."""
    msg = await loader._extension_handler("cog2", load=True, unload=True)
    mock_bot.unload_extension.assert_called_once_with("app.extensions.cog2.cog")
    mock_bot.load_extension.assert_called_once_with("app.extensions.cog2.cog")
    assert "**`cog2` reloaded.**" in msg


@pytest.mark.asyncio
async def test_extension_handler_errors(loader, mock_bot):
    """Verifies that errors during load and unload are gracefully caught and reported."""
    # Simulate a load error
    mock_bot.load_extension.side_effect = Exception("LoadError")
    msg = await loader._extension_handler("cog2", load=True, unload=False)
    assert "**ERROR loading!:**" in msg

    # Simulate an unload error
    mock_bot.unload_extension.side_effect = Exception("UnloadError")
    msg = await loader._extension_handler("cog2", load=False, unload=True)
    assert "**ERROR unloading!:**" in msg


@pytest.mark.asyncio
async def test_power_commands(loader):
    """Tests the slash commands (load, unload, reload) to ensure they defer, call the handler, and respond."""
    mock_interaction = MagicMock()
    mock_interaction.response.defer = AsyncMock()
    mock_interaction.followup.send = AsyncMock()

    with patch.object(loader, "_extension_handler", return_value="result") as mock_handler:
        # Test /load
        await loader.power_load(mock_interaction, "cog2")
        mock_handler.assert_called_with("cog2")
        mock_interaction.followup.send.assert_called_with("result")

        # Test /unload
        await loader.power_unload(mock_interaction, "cog2")
        mock_handler.assert_called_with("cog2", load=False, unload=True)

        # Test /reload
        await loader.power_reload(mock_interaction, "cog2")
        mock_handler.assert_called_with("cog2", load=True, unload=True)


@pytest.mark.asyncio
async def test_list_cogs(loader):
    """Tests the autocomplete behavior for cog names."""
    mock_interaction = MagicMock()
    mock_interaction.response.send_autocomplete = AsyncMock()

    # Test empty input returns all options
    await loader.list_cogs(mock_interaction, "")
    mock_interaction.response.send_autocomplete.assert_called_with(["cog1", "cog2"])

    # Test partial input matching multiple options
    await loader.list_cogs(mock_interaction, "cog")
    mock_interaction.response.send_autocomplete.assert_called_with(["cog1", "cog2"])

    # Test specific input matching one option
    await loader.list_cogs(mock_interaction, "cog1")
    mock_interaction.response.send_autocomplete.assert_called_with(["cog1"])
