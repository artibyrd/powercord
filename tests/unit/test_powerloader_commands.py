"""Unit tests for AppPowerLoader slash commands: delete_server_data and api_access_*.

Covers the Discord slash commands in powerloader.py that manage extension data
deletion and API role-based access control (RBAC).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot.powerloader import AppPowerLoader, ConfirmDeleteView

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_bot():
    """Provides a mocked bot with minimal cog_report for PowerLoader init."""
    bot = MagicMock()
    bot.cog_report = {
        "all_cogs": ["utilities", "example"],
        "cog_custom_contexts": {},
        "cog_persistent_modals": {},
        "cog_persistent_views": {},
    }
    return bot


@pytest.fixture
def loader(mock_bot):
    """An AppPowerLoader instance backed by the mock bot."""
    return AppPowerLoader(mock_bot)


@pytest.fixture
def mock_interaction():
    """A mocked Discord Interaction with guild context."""
    interaction = MagicMock()
    interaction.guild = MagicMock()
    interaction.guild.id = 12345
    interaction.response.send_message = AsyncMock()
    interaction.edit_original_message = AsyncMock()
    return interaction


@pytest.fixture
def mock_interaction_no_guild():
    """A mocked Discord Interaction with no guild (DM context)."""
    interaction = MagicMock()
    interaction.guild = None
    interaction.response.send_message = AsyncMock()
    return interaction


# ── ConfirmDeleteView ─────────────────────────────────────────────────


class TestConfirmDeleteView:
    """Tests for the confirmation prompt view's structure.

    Note: The @nextcord.ui.button decorator wraps callbacks as Button objects,
    making direct invocation in unit tests fragile across library versions.
    We test the view's initialization and structural properties instead.
    These tests must be async because nextcord.ui.View requires an event loop.
    """

    @pytest.mark.asyncio
    async def test_initial_value_is_none(self) -> None:
        """View value should start as None before any button press."""
        view = ConfirmDeleteView()
        assert view.value is None

    @pytest.mark.asyncio
    async def test_timeout_is_set(self) -> None:
        """View should have a 30-second timeout to prevent stale prompts."""
        view = ConfirmDeleteView()
        assert view.timeout == 30


# ── delete_server_data ────────────────────────────────────────────────


class TestDeleteServerData:
    """Tests for the /powercord delete_server_data command."""

    @pytest.mark.asyncio
    async def test_no_guild_rejects(self, loader, mock_interaction_no_guild) -> None:
        """DM usage should be rejected with an ephemeral message."""
        await loader.delete_server_data(mock_interaction_no_guild, "utilities")
        mock_interaction_no_guild.response.send_message.assert_called_once()
        assert "must be used in a server" in str(mock_interaction_no_guild.response.send_message.call_args)

    @pytest.mark.asyncio
    @patch("app.bot.powerloader.get_deletable_extensions", return_value=["utilities"])
    async def test_invalid_extension_rejects(self, _mock_del, loader, mock_interaction) -> None:
        """Requesting deletion for an unsupported extension should be rejected."""
        await loader.delete_server_data(mock_interaction, "nonexistent")
        assert "does not support data deletion" in str(mock_interaction.response.send_message.call_args)

    @pytest.mark.asyncio
    @patch("app.bot.powerloader.run_hook")
    @patch("app.bot.powerloader.get_deletable_extensions", return_value=["utilities"])
    async def test_confirmed_deletion_runs_hook(self, _mock_del, mock_run_hook, loader, mock_interaction) -> None:
        """Confirming deletion should call run_hook with the correct args."""
        # Patch ConfirmDeleteView to immediately confirm
        with patch("app.bot.powerloader.ConfirmDeleteView") as MockView:
            view_instance = MagicMock()
            view_instance.value = True
            view_instance.wait = AsyncMock()
            MockView.return_value = view_instance

            await loader.delete_server_data(mock_interaction, "utilities")

            mock_run_hook.assert_called_once_with("utilities", "delete_guild_data", guild_id=12345)
            # Should edit with success message
            mock_interaction.edit_original_message.assert_called_once()
            assert "deleted" in str(mock_interaction.edit_original_message.call_args).lower()

    @pytest.mark.asyncio
    @patch("app.bot.powerloader.get_deletable_extensions", return_value=["utilities"])
    async def test_cancelled_deletion(self, _mock_del, loader, mock_interaction) -> None:
        """Cancelling deletion should show cancellation message."""
        with patch("app.bot.powerloader.ConfirmDeleteView") as MockView:
            view_instance = MagicMock()
            view_instance.value = False
            view_instance.wait = AsyncMock()
            MockView.return_value = view_instance

            await loader.delete_server_data(mock_interaction, "utilities")

            assert "cancelled" in str(mock_interaction.edit_original_message.call_args).lower()

    @pytest.mark.asyncio
    @patch("app.bot.powerloader.get_deletable_extensions", return_value=["utilities"])
    async def test_timeout_deletion(self, _mock_del, loader, mock_interaction) -> None:
        """View timeout (value=None) should show timeout message."""
        with patch("app.bot.powerloader.ConfirmDeleteView") as MockView:
            view_instance = MagicMock()
            view_instance.value = None
            view_instance.wait = AsyncMock()
            MockView.return_value = view_instance

            await loader.delete_server_data(mock_interaction, "utilities")

            assert "timed out" in str(mock_interaction.edit_original_message.call_args).lower()


# ── autocomplete_deletable_extensions ─────────────────────────────────


class TestAutocompleteDeletableExtensions:
    """Tests for the deletable extensions autocomplete handler."""

    @pytest.mark.asyncio
    @patch("app.bot.powerloader.get_deletable_extensions", return_value=["utilities", "honeypot"])
    async def test_empty_input_returns_all(self, _mock_del, loader, mock_interaction) -> None:
        """Empty input should return all deletable extensions."""
        mock_interaction.response.send_autocomplete = AsyncMock()
        await loader.autocomplete_deletable_extensions(mock_interaction, "")
        mock_interaction.response.send_autocomplete.assert_called_with(["utilities", "honeypot"])

    @pytest.mark.asyncio
    @patch("app.bot.powerloader.get_deletable_extensions", return_value=["utilities", "honeypot"])
    async def test_partial_input_filters(self, _mock_del, loader, mock_interaction) -> None:
        """Partial input should filter to matching extensions."""
        mock_interaction.response.send_autocomplete = AsyncMock()
        await loader.autocomplete_deletable_extensions(mock_interaction, "util")
        mock_interaction.response.send_autocomplete.assert_called_with(["utilities"])


# ── _get_api_scopes ───────────────────────────────────────────────────


class TestGetApiScopes:
    """Tests for the private scope list helper."""

    @patch.object(AppPowerLoader, "__init__", lambda self, bot: None)
    def test_returns_global_default_plus_extensions(self) -> None:
        """Should return ['global', 'default'] prepended to extension names."""
        loader = AppPowerLoader.__new__(AppPowerLoader)
        with patch("app.bot.powerloader.GadgetInspector") as MockInspector:
            MockInspector.return_value.inspect_extensions.return_value = {
                "utilities": ["cog", "widget"],
                "example": ["cog", "sprocket"],
            }
            scopes = loader._get_api_scopes()
            assert scopes[0] == "global"
            assert scopes[1] == "default"
            assert "utilities" in scopes
            assert "example" in scopes


# ── api_access_grant ──────────────────────────────────────────────────


class TestApiAccessGrant:
    """Tests for the /powercord api_access_grant command."""

    @pytest.mark.asyncio
    async def test_no_guild_rejects(self, loader, mock_interaction_no_guild) -> None:
        """DM usage should be rejected."""
        mock_role = MagicMock()
        await loader.api_access_grant(mock_interaction_no_guild, role=mock_role, scope="global")
        assert "must be used in a server" in str(mock_interaction_no_guild.response.send_message.call_args)

    @pytest.mark.asyncio
    async def test_invalid_scope_rejects(self, loader, mock_interaction) -> None:
        """Invalid scope should be rejected."""
        mock_role = MagicMock()
        with patch.object(loader, "_get_api_scopes", return_value=["global", "default"]):
            await loader.api_access_grant(mock_interaction, role=mock_role, scope="nonexistent")
            assert "Invalid scope" in str(mock_interaction.response.send_message.call_args)

    @pytest.mark.asyncio
    async def test_duplicate_mapping_rejects(self, loader, mock_interaction) -> None:
        """Granting an already-assigned scope should be rejected."""
        mock_role = MagicMock()
        mock_role.id = 999
        mock_role.mention = "<@&999>"

        with patch.object(loader, "_get_api_scopes", return_value=["global", "default"]):
            with patch("app.bot.powerloader.init_connection_engine"):
                with patch("app.bot.powerloader.Session") as MockSession:
                    session = MagicMock()
                    MockSession.return_value.__enter__ = MagicMock(return_value=session)
                    MockSession.return_value.__exit__ = MagicMock(return_value=False)
                    # Simulate existing mapping found
                    session.exec.return_value.first.return_value = MagicMock()

                    await loader.api_access_grant(mock_interaction, role=mock_role, scope="global")
                    assert "already has" in str(mock_interaction.response.send_message.call_args)

    @pytest.mark.asyncio
    async def test_successful_grant(self, loader, mock_interaction) -> None:
        """A valid new grant should commit and confirm."""
        mock_role = MagicMock()
        mock_role.id = 999
        mock_role.mention = "<@&999>"

        with patch.object(loader, "_get_api_scopes", return_value=["global", "default"]):
            with patch("app.bot.powerloader.init_connection_engine"):
                with patch("app.bot.powerloader.Session") as MockSession:
                    session = MagicMock()
                    MockSession.return_value.__enter__ = MagicMock(return_value=session)
                    MockSession.return_value.__exit__ = MagicMock(return_value=False)
                    # No existing mapping
                    session.exec.return_value.first.return_value = None

                    await loader.api_access_grant(mock_interaction, role=mock_role, scope="global")
                    session.add.assert_called_once()
                    session.commit.assert_called_once()
                    assert "Granted" in str(mock_interaction.response.send_message.call_args)


# ── api_access_revoke ─────────────────────────────────────────────────


class TestApiAccessRevoke:
    """Tests for the /powercord api_access_revoke command."""

    @pytest.mark.asyncio
    async def test_no_guild_rejects(self, loader, mock_interaction_no_guild) -> None:
        """DM usage should be rejected."""
        mock_role = MagicMock()
        await loader.api_access_revoke(mock_interaction_no_guild, role=mock_role, scope="global")
        assert "must be used in a server" in str(mock_interaction_no_guild.response.send_message.call_args)

    @pytest.mark.asyncio
    async def test_invalid_scope_rejects(self, loader, mock_interaction) -> None:
        """Invalid scope should be rejected."""
        mock_role = MagicMock()
        with patch.object(loader, "_get_api_scopes", return_value=["global", "default"]):
            await loader.api_access_revoke(mock_interaction, role=mock_role, scope="bogus")
            assert "Invalid scope" in str(mock_interaction.response.send_message.call_args)

    @pytest.mark.asyncio
    async def test_not_found_rejects(self, loader, mock_interaction) -> None:
        """Revoking a scope that wasn't granted should be rejected."""
        mock_role = MagicMock()
        mock_role.id = 999
        mock_role.mention = "<@&999>"

        with patch.object(loader, "_get_api_scopes", return_value=["global"]):
            with patch("app.bot.powerloader.init_connection_engine"):
                with patch("app.bot.powerloader.Session") as MockSession:
                    session = MagicMock()
                    MockSession.return_value.__enter__ = MagicMock(return_value=session)
                    MockSession.return_value.__exit__ = MagicMock(return_value=False)
                    session.exec.return_value.first.return_value = None

                    await loader.api_access_revoke(mock_interaction, role=mock_role, scope="global")
                    assert "does not have" in str(mock_interaction.response.send_message.call_args)

    @pytest.mark.asyncio
    async def test_successful_revoke(self, loader, mock_interaction) -> None:
        """A valid revoke should delete the mapping and confirm."""
        mock_role = MagicMock()
        mock_role.id = 999
        mock_role.mention = "<@&999>"

        with patch.object(loader, "_get_api_scopes", return_value=["global"]):
            with patch("app.bot.powerloader.init_connection_engine"):
                with patch("app.bot.powerloader.Session") as MockSession:
                    session = MagicMock()
                    MockSession.return_value.__enter__ = MagicMock(return_value=session)
                    MockSession.return_value.__exit__ = MagicMock(return_value=False)
                    existing = MagicMock()
                    session.exec.return_value.first.return_value = existing

                    await loader.api_access_revoke(mock_interaction, role=mock_role, scope="global")
                    session.delete.assert_called_once_with(existing)
                    session.commit.assert_called_once()
                    assert "Revoked" in str(mock_interaction.response.send_message.call_args)


# ── api_access_list ───────────────────────────────────────────────────


class TestApiAccessList:
    """Tests for the /powercord api_access_list command."""

    @pytest.mark.asyncio
    async def test_no_guild_rejects(self, loader, mock_interaction_no_guild) -> None:
        """DM usage should be rejected."""
        await loader.api_access_list(mock_interaction_no_guild)
        assert "must be used in a server" in str(mock_interaction_no_guild.response.send_message.call_args)

    @pytest.mark.asyncio
    async def test_no_mappings_found(self, loader, mock_interaction) -> None:
        """No configured roles should return a friendly message."""
        with patch("app.bot.powerloader.init_connection_engine"):
            with patch("app.bot.powerloader.Session") as MockSession:
                session = MagicMock()
                MockSession.return_value.__enter__ = MagicMock(return_value=session)
                MockSession.return_value.__exit__ = MagicMock(return_value=False)
                session.exec.return_value.all.return_value = []

                await loader.api_access_list(mock_interaction)
                assert "No API access roles" in str(mock_interaction.response.send_message.call_args)

    @pytest.mark.asyncio
    async def test_mappings_returned_as_embed(self, loader, mock_interaction) -> None:
        """Existing mappings should be displayed in an embed."""
        mapping = MagicMock()
        mapping.role_id = 999
        mapping.extension_name = "global"

        with patch("app.bot.powerloader.init_connection_engine"):
            with patch("app.bot.powerloader.Session") as MockSession:
                session = MagicMock()
                MockSession.return_value.__enter__ = MagicMock(return_value=session)
                MockSession.return_value.__exit__ = MagicMock(return_value=False)
                session.exec.return_value.all.return_value = [mapping]

                await loader.api_access_list(mock_interaction)
                call_kwargs = mock_interaction.response.send_message.call_args
                # Should have been called with an embed keyword
                assert "embed" in str(call_kwargs)


# ── autocomplete_grant_scopes / autocomplete_revoke_scopes ────────────


class TestAutocompleteScopes:
    """Tests for the scope autocomplete handlers (grant and revoke share logic)."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_all_scopes(self, loader, mock_interaction) -> None:
        """Empty scope input should return all scopes (capped at 25)."""
        mock_interaction.response.send_autocomplete = AsyncMock()
        with patch.object(loader, "_get_api_scopes", return_value=["global", "default", "utilities"]):
            await loader.autocomplete_grant_scopes(mock_interaction, "")
            mock_interaction.response.send_autocomplete.assert_called_with(["global", "default", "utilities"])

    @pytest.mark.asyncio
    async def test_partial_input_filters_scopes(self, loader, mock_interaction) -> None:
        """Partial input should filter to matching scopes."""
        mock_interaction.response.send_autocomplete = AsyncMock()
        with patch.object(loader, "_get_api_scopes", return_value=["global", "default", "utilities"]):
            await loader.autocomplete_revoke_scopes(mock_interaction, "gl")
            mock_interaction.response.send_autocomplete.assert_called_with(["global"])
