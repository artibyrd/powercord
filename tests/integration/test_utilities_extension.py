import json
from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest
from sqlmodel import Session, SQLModel, delete, select

from app.common.alchemy import init_connection_engine
from app.db.models import DiscordChannel, DiscordRole
from app.extensions.example.widget import admin_example_controls_widget
from app.extensions.utilities.cog import UtilitiesCog
from app.extensions.utilities.widget import (
    guild_admin_audit_channels_widget,
    guild_admin_audit_permissions_widget,
    guild_admin_audit_roles_widget,
    guild_admin_security_overview_widget,
)

# All tests in this module are integration tests.
pytestmark = pytest.mark.integration

engine = init_connection_engine()


@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ... (audit test remains mostly same) ...


def test_admin_example_controls_widget():
    """Verify example controls widget renders correctly."""
    card = admin_example_controls_widget()
    assert card is not None
    # Assuming Card returns some object or string representation
    # In a real scenario we might inspect the content for "Start Counters"


def test_guild_admin_audit_widgets(session):
    # 1. Insert Test Data
    session.exec(delete(DiscordRole).where(DiscordRole.guild_id == 999))
    session.exec(delete(DiscordChannel).where(DiscordChannel.guild_id == 999))
    session.commit()

    # Test Empty State
    card_roles_empty = guild_admin_audit_roles_widget(999)
    assert card_roles_empty is not None
    card_channels_empty = guild_admin_audit_channels_widget(999)
    assert card_channels_empty is not None
    card_security_empty = guild_admin_security_overview_widget(999)
    assert card_security_empty is not None
    card_permissions_empty = guild_admin_audit_permissions_widget(999)
    assert card_permissions_empty is not None

    # Complex role with admin perms, color, and flags
    role = DiscordRole(
        id=901,
        guild_id=999,
        name="WidgetRole",
        permissions=8,  # Administrator
        position=1,
        color=16711680,
        is_hoisted=True,
        is_managed=True,
        is_mentionable=True,
    )
    # Channel with complex overwrites to trigger overwrites_ui parsing
    complex_overwrites = json.dumps(
        {
            "999": {"deny": 1024, "name": "@everyone"},  # Deny View Channel (private)
            "901": {"allow": 1024, "deny": 0, "name": "WidgetRole"},  # Allow View Channel
        }
    )
    chan_cat = DiscordChannel(
        id=902,
        guild_id=999,
        parent_id=None,
        name="WidgetCat",
        type="category",
        position=0,
        overwrites=complex_overwrites,
    )
    chan_text = DiscordChannel(
        id=903, guild_id=999, parent_id=902, name="WidgetChan", type="text", position=1, overwrites=complex_overwrites
    )
    session.add(role)
    session.add(chan_cat)
    session.add(chan_text)
    session.commit()

    # 2. Render Widget with Data
    card_roles = guild_admin_audit_roles_widget(999)
    assert card_roles is not None

    card_channels = guild_admin_audit_channels_widget(999)
    assert card_channels is not None

    card_security = guild_admin_security_overview_widget(999)
    assert card_security is not None

    card_permissions = guild_admin_audit_permissions_widget(999)
    assert card_permissions is not None

    # Clean up
    session.exec(delete(DiscordRole).where(DiscordRole.guild_id == 999))
    session.exec(delete(DiscordChannel).where(DiscordChannel.guild_id == 999))
    session.commit()


@pytest.mark.asyncio
async def test_utilities_audit_guild(session):
    """
    Test the internal `audit_guild` engine function of the Utilities Cog.

    Verifies that:
    1. Processing a mock guild structure deletes old DB artifacts.
    2. Accurately serializes guild roles and overwrites into `DiscordRole` and `DiscordChannel` models.
    """
    # 1. Setup Mock Guild
    mock_guild = MagicMock(spec=nextcord.Guild)
    mock_guild.id = 123456789
    mock_guild.name = "Test Guild"

    # Mock Role
    mock_role = MagicMock(spec=nextcord.Role)
    mock_role.id = 101
    mock_role.name = "Admin"
    mock_role.permissions.value = 8
    mock_role.position = 10
    mock_role.color.value = 0xFF0000
    mock_role.hoist = True
    mock_role.managed = False
    mock_role.mentionable = True
    mock_guild.roles = [mock_role]

    # Mock Category
    mock_cat = MagicMock(spec=nextcord.CategoryChannel)
    mock_cat.id = 201
    mock_cat.name = "Categories"
    mock_cat.type = nextcord.ChannelType.category
    mock_cat.position = 0
    mock_cat.category_id = None
    mock_cat.overwrites = {}

    # Mock Text Channel in Category
    mock_chan = MagicMock(spec=nextcord.TextChannel)
    mock_chan.id = 301
    mock_chan.name = "general"
    mock_chan.type = nextcord.ChannelType.text
    mock_chan.position = 1
    mock_chan.category_id = 201

    # Mock Overwrite
    mock_overwrite = MagicMock()
    mock_overwrite.pair.return_value = (MagicMock(value=100), MagicMock(value=0))
    mock_chan.overwrites = {mock_role: mock_overwrite}

    mock_guild.channels = [mock_cat, mock_chan]

    # 2. Run Audit
    bot = MagicMock()
    cog = UtilitiesCog(bot)
    await cog.audit_guild(mock_guild)

    # 3. Verify DB Data
    roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == 123456789)).all()
    channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == 123456789)).all()

    assert len(roles) == 1
    assert roles[0].name == "Admin"

    assert len(channels) == 2
    cat_db = next(c for c in channels if c.id == 201)
    chan_db = next(c for c in channels if c.id == 301)

    assert cat_db.name == "Categories"
    assert chan_db.parent_id == 201

    # Verify overwrites serialization
    ov = json.loads(chan_db.overwrites)
    assert str(101) in ov
    assert ov[str(101)]["allow"] == 100

    # Verify overwrites serialization
    ov = json.loads(chan_db.overwrites)
    assert str(101) in ov
    assert ov[str(101)]["allow"] == 100


def test_verify_bot_permissions():
    """Verify permission check logic."""
    bot = MagicMock()
    cog = UtilitiesCog(bot)

    # Case 1: Missing permissions
    mock_guild_missing = MagicMock()
    mock_guild_missing.me.guild_permissions.manage_roles = False
    mock_guild_missing.me.guild_permissions.manage_channels = False
    mock_guild_missing.me.guild_permissions.administrator = False

    missing = cog.verify_bot_permissions(mock_guild_missing)
    assert "Manage Roles" in missing
    assert "Manage Channels" in missing

    # Case 2: Has Administrator (overrides all)
    mock_guild_admin = MagicMock()
    mock_guild_admin.me.guild_permissions.manage_roles = False  # Even if false
    mock_guild_admin.me.guild_permissions.administrator = True

    missing_admin = cog.verify_bot_permissions(mock_guild_admin)
    assert len(missing_admin) == 0

    # Case 3: Has specific permissions
    mock_guild_ok = MagicMock()
    mock_guild_ok.me.guild_permissions.manage_roles = True
    mock_guild_ok.me.guild_permissions.manage_channels = True
    mock_guild_ok.me.guild_permissions.administrator = False

    missing_ok = cog.verify_bot_permissions(mock_guild_ok)
    assert len(missing_ok) == 0


@pytest.mark.asyncio
async def test_manual_audit_success():
    """Verify standard success path where manual audit triggers guild synchronization."""
    bot = MagicMock()
    cog = UtilitiesCog(bot)
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.send = AsyncMock()
    ctx.typing = MagicMock()
    ctx.typing.return_value.__aenter__ = AsyncMock()
    ctx.typing.return_value.__aexit__ = AsyncMock()

    with patch.object(cog, "verify_bot_permissions", return_value=[]):
        with patch.object(cog, "audit_guild", new_callable=AsyncMock) as mock_audit:
            await cog.manual_audit(cog, ctx)

            mock_audit.assert_called_once_with(ctx.guild)
            ctx.send.assert_any_call("✅ Audit complete! Dashboard updated.")


@pytest.mark.asyncio
async def test_manual_audit_missing_perms():
    """Verify manual audit aborts correctly if the bot lacks Admin/Manage Server permissions."""
    bot = MagicMock()
    cog = UtilitiesCog(bot)
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.send = AsyncMock()

    with patch.object(cog, "verify_bot_permissions", return_value=["Manage Roles"]):
        await cog.manual_audit(cog, ctx)

        ctx.send.assert_called_once_with("❌ Bot is missing permissions: Manage Roles")


@pytest.mark.asyncio
async def test_manual_audit_failure():
    """Verify manual audit handles DB or Server exceptions elegantly rather than crashing."""
    bot = MagicMock()
    cog = UtilitiesCog(bot)
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.send = AsyncMock()
    ctx.typing = MagicMock()
    ctx.typing.return_value.__aenter__ = AsyncMock()
    ctx.typing.return_value.__aexit__ = AsyncMock()

    with patch.object(cog, "verify_bot_permissions", return_value=[]):
        with patch.object(cog, "audit_guild", new_callable=AsyncMock, side_effect=Exception("TestError")):
            await cog.manual_audit(cog, ctx)

            ctx.send.assert_any_call("❌ Audit failed: TestError")


@pytest.mark.asyncio
async def test_slash_audit_success():
    """Verify slash command wrapper for audit passes the correct contexts downstream."""
    bot = MagicMock()
    cog = UtilitiesCog(bot)
    interaction = MagicMock(spec=nextcord.Interaction)
    interaction.guild = MagicMock()
    interaction.user = MagicMock(spec=nextcord.Member)
    interaction.user.guild_permissions.administrator = True
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    with patch.object(cog, "verify_bot_permissions", return_value=[]):
        with patch.object(cog, "audit_guild", new_callable=AsyncMock) as mock_audit:
            await cog.slash_audit(interaction)

            interaction.response.defer.assert_called_once()
            mock_audit.assert_called_once_with(interaction.guild)
            interaction.followup.send.assert_called_with("✅ Audit complete! Dashboard updated.")


@pytest.mark.asyncio
async def test_slash_audit_not_in_guild():
    """Verify slash audit correctly bounces users attempting to run it in DMs."""
    bot = MagicMock()
    cog = UtilitiesCog(bot)
    interaction = MagicMock(spec=nextcord.Interaction)
    interaction.guild = None
    interaction.response.send_message = AsyncMock()

    await cog.slash_audit(interaction)
    interaction.response.send_message.assert_called_once_with(
        "❌ This command must be used in a server.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_slash_audit_no_admin():
    """Verify slash audit bounces unauthorized users lacking administrative server powers."""
    bot = MagicMock()
    cog = UtilitiesCog(bot)
    interaction = MagicMock(spec=nextcord.Interaction)
    interaction.guild = MagicMock()
    interaction.user = MagicMock(spec=nextcord.Member)
    interaction.user.guild_permissions.administrator = False
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    await cog.slash_audit(interaction)
    interaction.followup.send.assert_called_once_with("❌ You need Administrator permissions to use this command.")


@pytest.mark.asyncio
async def test_slash_audit_bot_missing_perms():
    bot = MagicMock()
    cog = UtilitiesCog(bot)
    interaction = MagicMock(spec=nextcord.Interaction)
    interaction.guild = MagicMock()
    interaction.user = MagicMock(spec=nextcord.Member)
    interaction.user.guild_permissions.administrator = True
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    with patch.object(cog, "verify_bot_permissions", return_value=["Manage Roles"]):
        await cog.slash_audit(interaction)
        interaction.followup.send.assert_called_once_with("❌ Bot is missing permissions: Manage Roles")


@pytest.mark.asyncio
async def test_slash_audit_failure():
    bot = MagicMock()
    cog = UtilitiesCog(bot)
    interaction = MagicMock(spec=nextcord.Interaction)
    interaction.guild = MagicMock()
    interaction.user = MagicMock(spec=nextcord.Member)
    interaction.user.guild_permissions.administrator = True
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    with patch.object(cog, "verify_bot_permissions", return_value=[]):
        with patch.object(cog, "audit_guild", new_callable=AsyncMock, side_effect=Exception("TestError")):
            await cog.slash_audit(interaction)
            interaction.followup.send.assert_called_with("❌ Audit failed: TestError")
