"""Tests for the extension lifecycle hook registry and data deletion logic.

Covers: hook registration, supports_delete_data, get_deletable_extensions,
run_hook (including core settings cleanup), and concrete extension hooks
for the utilities extension.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import select

from app.common.extension_hooks import (
    _hooks,
    get_deletable_extensions,
    register_hook,
    run_hook,
    supports_delete_data,
)
from app.db.models import GuildExtensionSettings, WidgetSettings

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_hooks():
    """Ensure the global hook registry is reset between tests."""
    saved = dict(_hooks)
    _hooks.clear()
    yield
    _hooks.clear()
    _hooks.update(saved)


# ── Registry Unit Tests ───────────────────────────────────────────────


def test_register_and_run_hook():
    """Registering a hook and running it invokes the callback."""
    callback = MagicMock()
    register_hook("test_ext", "delete_guild_data", callback)
    run_hook("test_ext", "delete_guild_data", guild_id=42)
    callback.assert_called_once_with(guild_id=42)


def test_supports_delete_data_true():
    """supports_delete_data returns True when a hook is registered."""
    register_hook("some_ext", "delete_guild_data", lambda **kw: None)
    assert supports_delete_data("some_ext") is True


def test_supports_delete_data_false():
    """supports_delete_data returns False for extensions without a hook."""
    assert supports_delete_data("nonexistent_ext") is False


def test_get_deletable_extensions():
    """get_deletable_extensions returns a sorted list of registered extensions."""
    register_hook("zeta", "delete_guild_data", lambda **kw: None)
    register_hook("alpha", "delete_guild_data", lambda **kw: None)
    register_hook("alpha", "other_event", lambda **kw: None)
    assert get_deletable_extensions() == ["alpha", "zeta"]


def test_run_unregistered_hook():
    """Running a hook for an unregistered extension is a no-op (no crash)."""
    # Should not raise
    run_hook("missing_ext", "delete_guild_data", guild_id=1)


def test_hook_exception_is_swallowed():
    """If a hook callback raises, the error is logged but not propagated."""

    def bad_hook(**kwargs):
        raise RuntimeError("boom")

    register_hook("bad_ext", "delete_guild_data", bad_hook)
    # Should not raise
    run_hook("bad_ext", "delete_guild_data", guild_id=1)


# ── Core Settings Cleanup Tests ───────────────────────────────────────


def test_core_settings_cleanup(session):
    """Running delete_guild_data cleans up GuildExtensionSettings and WidgetSettings."""
    guild_id = 555
    ext_name = "cleanup_test"

    # Populate core settings
    session.add(GuildExtensionSettings(guild_id=guild_id, extension_name=ext_name, gadget_type="cog", is_enabled=True))
    session.add(
        WidgetSettings(
            guild_id=guild_id,
            extension_name=ext_name,
            widget_name="test_widget",
            is_enabled=True,
        )
    )
    # Also add a row for a DIFFERENT guild to ensure it survives
    session.add(GuildExtensionSettings(guild_id=999, extension_name=ext_name, gadget_type="cog", is_enabled=True))
    session.commit()

    # Register a dummy hook and run it
    register_hook(ext_name, "delete_guild_data", lambda **kw: None)

    # Patch init_connection_engine to return the test engine
    with patch("app.common.extension_hooks.init_connection_engine", return_value=session.get_bind()):
        run_hook(ext_name, "delete_guild_data", guild_id=guild_id)

    # Verify target rows are gone
    remaining_ges = session.exec(
        select(GuildExtensionSettings).where(
            GuildExtensionSettings.guild_id == guild_id,
            GuildExtensionSettings.extension_name == ext_name,
        )
    ).all()
    assert len(remaining_ges) == 0

    remaining_ws = session.exec(
        select(WidgetSettings).where(
            WidgetSettings.guild_id == guild_id,
            WidgetSettings.extension_name == ext_name,
        )
    ).all()
    assert len(remaining_ws) == 0

    # Verify OTHER guild rows survived
    other = session.exec(
        select(GuildExtensionSettings).where(
            GuildExtensionSettings.guild_id == 999,
        )
    ).all()
    assert len(other) == 1


# ── Utilities Hook Integration Test ──────────────────────────────────


def test_utilities_delete_guild_data(session):
    """The utilities extension hook deletes all guild-specific audit rows."""
    from app.db.models import DiscordChannel, DiscordRole

    guild_id = 666

    # Populate audit data
    session.add(
        DiscordRole(
            id=1,
            guild_id=guild_id,
            name="Admin",
            permissions=8,
        )
    )
    session.add(
        DiscordChannel(
            id=10,
            guild_id=guild_id,
            name="general",
            type="text",
        )
    )
    # Data for a different guild
    session.add(
        DiscordRole(
            id=2,
            guild_id=999,
            name="Mod",
            permissions=0,
        )
    )
    session.commit()

    from app.extensions.utilities import _delete_guild_data

    with patch("app.extensions.utilities.init_connection_engine", return_value=session.get_bind()):
        _delete_guild_data(guild_id=guild_id)

    assert len(session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()) == 0
    assert len(session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()) == 0

    # Other guild intact
    assert len(session.exec(select(DiscordRole).where(DiscordRole.guild_id == 999)).all()) == 1


# ── Powerloader Slash Command Tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_delete_server_data_no_guild():
    """The slash command rejects usage outside a guild."""
    from app.bot.powerloader import AppPowerLoader

    mock_bot = MagicMock()
    mock_bot.cog_report = {"all_cogs": []}
    loader = AppPowerLoader(mock_bot)

    interaction = MagicMock()
    interaction.guild = None
    interaction.response = MagicMock()
    interaction.response.send_message = MagicMock(return_value=None)

    # Patch the coroutine
    from unittest.mock import AsyncMock

    interaction.response.send_message = AsyncMock()

    await loader.delete_server_data.callback(loader, interaction, extension="honeypot")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "must be used in a server" in str(call_kwargs)


@pytest.mark.asyncio
async def test_delete_server_data_unsupported_extension():
    """The slash command rejects extensions that don't support deletion."""
    from unittest.mock import AsyncMock

    from app.bot.powerloader import AppPowerLoader

    mock_bot = MagicMock()
    mock_bot.cog_report = {"all_cogs": []}
    loader = AppPowerLoader(mock_bot)

    interaction = MagicMock()
    interaction.guild = MagicMock()
    interaction.guild.id = 123
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    await loader.delete_server_data.callback(loader, interaction, extension="nonexistent")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "does not support data deletion" in str(call_kwargs)


@pytest.mark.asyncio
async def test_autocomplete_deletable_extensions():
    """The autocomplete handler returns only deletable extensions."""
    from unittest.mock import AsyncMock

    from app.bot.powerloader import AppPowerLoader

    register_hook("honeypot", "delete_guild_data", lambda **kw: None)
    register_hook("utilities", "delete_guild_data", lambda **kw: None)

    mock_bot = MagicMock()
    mock_bot.cog_report = {"all_cogs": []}
    loader = AppPowerLoader(mock_bot)

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_autocomplete = AsyncMock()

    # Full list (empty query)
    await loader.autocomplete_deletable_extensions(interaction, extension="")
    interaction.response.send_autocomplete.assert_called_with(["honeypot", "utilities"])

    # Filtered by prefix
    interaction.response.send_autocomplete.reset_mock()
    await loader.autocomplete_deletable_extensions(interaction, extension="hon")
    interaction.response.send_autocomplete.assert_called_with(["honeypot"])
