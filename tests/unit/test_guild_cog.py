"""Unit tests for GuildAwareCog per-guild gating."""

from unittest.mock import MagicMock, patch

import pytest
from nextcord.ext import commands

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Concrete subclass for testing (simulates app.extensions.example.cog)
# ---------------------------------------------------------------------------
class _FakeCog(commands.Cog):
    """Minimal concrete cog to test GuildAwareCog behaviour.

    We import GuildAwareCog inside the tests so the module-path derivation
    won't match a real extension.  Instead we monkey-patch _extension_name.
    """


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def guild_cog():
    """Create a GuildAwareCog with a mocked bot and a known extension name."""
    from app.common.guild_cog import GuildAwareCog

    bot = MagicMock(spec=commands.Bot)
    cog = GuildAwareCog(bot)
    cog._extension_name = "example"  # Simulate the auto-derived name
    return cog


# ---------------------------------------------------------------------------
# Tests: extension name derivation
# ---------------------------------------------------------------------------


def test_extension_name_derived_from_module():
    """Verify _extension_name is derived from the module path when possible."""
    from app.common.guild_cog import GuildAwareCog

    bot = MagicMock(spec=commands.Bot)
    cog = GuildAwareCog(bot)

    # GuildAwareCog lives at app.common.guild_cog, so the fallback should be used
    # since there's no "extensions" segment in the module path.
    assert isinstance(cog._extension_name, str)
    assert len(cog._extension_name) > 0


# ---------------------------------------------------------------------------
# Tests: guild_enabled
# ---------------------------------------------------------------------------


@patch("app.ui.helpers.is_gadget_enabled", return_value=True)
def test_guild_enabled_true(mock_enabled, guild_cog):
    """Verify guild_enabled returns True when is_gadget_enabled returns True."""
    assert guild_cog.guild_enabled(12345) is True
    mock_enabled.assert_called_once_with(12345, "example", "cog")


@patch("app.ui.helpers.is_gadget_enabled", return_value=False)
def test_guild_enabled_false(mock_enabled, guild_cog):
    """Verify guild_enabled returns False when is_gadget_enabled returns False."""
    assert guild_cog.guild_enabled(12345) is False
    mock_enabled.assert_called_once_with(12345, "example", "cog")


def test_guild_enabled_none_guild_id(guild_cog):
    """Verify guild_enabled returns True for DMs (guild_id=None)."""
    assert guild_cog.guild_enabled(None) is True


# ---------------------------------------------------------------------------
# Tests: cog_check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.ui.helpers.is_gadget_enabled", return_value=True)
async def test_cog_check_enabled(mock_enabled, guild_cog):
    """Verify cog_check passes when cog is enabled for the guild."""
    ctx = MagicMock()
    ctx.guild.id = 99999
    result = await guild_cog.cog_check(ctx)
    assert result is True


@pytest.mark.asyncio
@patch("app.ui.helpers.is_gadget_enabled", return_value=False)
async def test_cog_check_disabled(mock_enabled, guild_cog):
    """Verify cog_check blocks when cog is disabled for the guild."""
    ctx = MagicMock()
    ctx.guild.id = 99999
    result = await guild_cog.cog_check(ctx)
    assert result is False


@pytest.mark.asyncio
async def test_cog_check_dm(guild_cog):
    """Verify cog_check passes in DMs (no guild)."""
    ctx = MagicMock()
    ctx.guild = None
    result = await guild_cog.cog_check(ctx)
    assert result is True


# ---------------------------------------------------------------------------
# Tests: interaction_check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.ui.helpers.is_gadget_enabled", return_value=True)
async def test_interaction_check_enabled(mock_enabled, guild_cog):
    """Verify interaction_check passes when cog is enabled for the guild."""
    interaction = MagicMock()
    interaction.guild_id = 99999
    result = await guild_cog.interaction_check(interaction)
    assert result is True


@pytest.mark.asyncio
@patch("app.ui.helpers.is_gadget_enabled", return_value=False)
async def test_interaction_check_disabled(mock_enabled, guild_cog):
    """Verify interaction_check blocks when cog is disabled for the guild."""
    interaction = MagicMock()
    interaction.guild_id = 99999
    result = await guild_cog.interaction_check(interaction)
    assert result is False


@pytest.mark.asyncio
async def test_interaction_check_dm(guild_cog):
    """Verify interaction_check passes in DMs (guild_id=None)."""
    interaction = MagicMock()
    interaction.guild_id = None
    result = await guild_cog.interaction_check(interaction)
    assert result is True
