import json
from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest

from app.db.models import DiscordAuditorConfig
from app.extensions.utilities.cog import UtilitiesCog

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
@patch("app.extensions.utilities.cog.Session")
async def test_slash_audit_config_get_empty(mock_session_cls):
    """Test getting configuration when none exists in the DB."""
    bot = MagicMock()
    cog = UtilitiesCog(bot)

    interaction = MagicMock(spec=nextcord.Interaction)
    interaction.guild.id = 12345
    # Mock administrator permission
    interaction.user = MagicMock(spec=nextcord.Member)
    interaction.user.guild_permissions.administrator = True
    interaction.response.send_message = AsyncMock()

    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session
    mock_session.exec.return_value.first.return_value = None  # No config

    await cog.slash_audit_config_get(interaction)

    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert "No auditor configuration found" in args[0] or kwargs.get("ephemeral")


@pytest.mark.asyncio
@patch("app.extensions.utilities.cog.Session")
async def test_slash_audit_config_get_existing(mock_session_cls):
    """Test getting configuration when it exists."""
    bot = MagicMock()
    cog = UtilitiesCog(bot)

    interaction = MagicMock(spec=nextcord.Interaction)
    interaction.guild.id = 12345
    interaction.user = MagicMock(spec=nextcord.Member)
    interaction.user.guild_permissions.administrator = True
    interaction.response.send_message = AsyncMock()

    # Mock role resolution
    mock_role = MagicMock(spec=nextcord.Role)
    mock_role.mention = "<@&999>"
    interaction.guild.get_role.return_value = mock_role

    # Mock channel resolution
    mock_channel = MagicMock(spec=nextcord.TextChannel)
    mock_channel.mention = "<#888>"
    interaction.guild.get_channel.return_value = mock_channel

    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session
    mock_session.exec.return_value.first.return_value = DiscordAuditorConfig(
        guild_id=12345,
        staff_separator_role_id=999,
        staff_channel_ids="[888]",
        announcement_channel_ids="[777]",
    )

    await cog.slash_audit_config_get(interaction)

    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    embed = kwargs.get("embed")
    assert embed is not None
    assert embed.title == "Auditor Configuration"


@pytest.mark.asyncio
@patch("app.extensions.utilities.cog.Session")
async def test_slash_audit_config_set(mock_session_cls):
    """Test setting/updating configurations."""
    bot = MagicMock()
    cog = UtilitiesCog(bot)

    interaction = MagicMock(spec=nextcord.Interaction)
    interaction.guild.id = 12345
    interaction.user = MagicMock(spec=nextcord.Member)
    interaction.user.guild_permissions.administrator = True
    interaction.response.send_message = AsyncMock()

    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session
    existing_config = DiscordAuditorConfig(guild_id=12345)
    mock_session.exec.return_value.first.return_value = existing_config

    mock_role = MagicMock(spec=nextcord.Role)
    mock_role.id = 999

    await cog.slash_audit_config_set(
        interaction, separator_role=mock_role, staff_channels="1001, 1002", announcement_channels="2001"
    )

    # Verify updates in session
    assert existing_config.staff_separator_role_id == 999
    assert json.loads(existing_config.staff_channel_ids) == [1001, 1002]
    assert json.loads(existing_config.announcement_channel_ids) == [2001]
    mock_session.commit.assert_called_once()

    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert "updated successfully" in args[0]
