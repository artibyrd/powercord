# TODO: Enable mypy strict checking for this file (currently excluded in pyproject.toml)
from __future__ import annotations

from typing import TYPE_CHECKING

import nextcord
from nextcord import Interaction, SlashOption
from nextcord.ext import commands
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.common.extension_hooks import get_deletable_extensions, run_hook
from app.common.extension_loader import GadgetInspector
from app.db.models import ApiAccessRole

if TYPE_CHECKING:
    from app.main_bot import Bot


class ConfirmDeleteView(nextcord.ui.View):
    """A two-button confirmation prompt for destructive data deletion."""

    def __init__(self) -> None:
        super().__init__(timeout=30)
        self.value: bool | None = None

    @nextcord.ui.button(label="Confirm Delete", style=nextcord.ButtonStyle.danger)
    async def confirm(self, button: nextcord.ui.Button, interaction: nextcord.Interaction) -> None:
        await interaction.response.send_message("Deleting data...", ephemeral=True)
        self.value = True
        self.stop()

    @nextcord.ui.button(label="Cancel", style=nextcord.ButtonStyle.grey)
    async def cancel(self, button: nextcord.ui.Button, interaction: nextcord.Interaction) -> None:
        await interaction.response.send_message("Cancelled.", ephemeral=True)
        self.value = False
        self.stop()


class AppPowerLoader(commands.Cog):
    """Updated cog loader using slash commands"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.all_cogs = self.bot.cog_report.get("all_cogs", [])
        self.preload_required_map = {
            "contexts": self.bot.cog_report.get("cog_custom_contexts", {}),
            "modals": self.bot.cog_report.get("cog_persistent_modals", {}),
            "views": self.bot.cog_report.get("cog_persistent_views", {}),
        }

    def _get_guild_ids(self, bot: commands.Bot):
        guild_ids = []
        for guildname in bot.guilds:
            guild_ids.append(guildname.id)
        return guild_ids

    def _hotload_caution(self, cogname):
        for preload_dict in self.preload_required_map.values():
            if cogname in preload_dict:
                return True
        return False

    async def _cog_rollout(self):
        await self.bot.rollout_application_commands()
        for guild in self.bot.guilds:
            await guild.rollout_application_commands()

    async def _extension_handler(self, cogname: str, load=True, unload=False):
        if self._hotload_caution(cogname):
            return f"**WARNING!:** `{cogname}` has registered preload requirements and cannot be hot loaded/unloaded/reloaded!  This cog must be enabled or disabled on bot startup instead."

        cog_path = f"app.extensions.{cogname}.cog"

        if unload:
            try:
                self.bot.unload_extension(cog_path)
            except Exception as e:
                return f"**ERROR unloading!:** `{type(e).__name__} - {e}`"

        if load:
            try:
                self.bot.load_extension(cog_path)
            except Exception as e:
                return f"**ERROR loading!:** `{type(e).__name__} - {e}`"

        await self._cog_rollout()

        if load and unload:
            return f"**`{cogname}` reloaded.**"
        elif load:
            return f"**`{cogname}` loaded.**"
        elif unload:
            return f"**`{cogname}` unloaded.**"

        return "No action performed."  # Should be unreachable

    @nextcord.slash_command(name="load", description="Load a cog", default_member_permissions=0)
    @commands.is_owner()
    async def power_load(
        self,
        interaction: Interaction,
        cogname: str = SlashOption(name="cogname", description="Cog name to load"),
    ):
        await interaction.response.defer()
        response_message = await self._extension_handler(cogname)
        await interaction.followup.send(response_message)

    @nextcord.slash_command(name="unload", description="Unload a cog", default_member_permissions=0)
    @commands.is_owner()
    async def power_unload(
        self,
        interaction: Interaction,
        cogname: str = SlashOption(name="cogname", description="Cog name to unload"),
    ):
        await interaction.response.defer()
        response_message = await self._extension_handler(cogname, load=False, unload=True)
        await interaction.followup.send(response_message)

    @nextcord.slash_command(name="reload", description="Reload a cog", default_member_permissions=0)
    @commands.is_owner()
    async def power_reload(
        self,
        interaction: Interaction,
        cogname: str = SlashOption(name="cogname", description="Cog name to reload"),
    ):
        await interaction.response.defer()
        response_message = await self._extension_handler(cogname, load=True, unload=True)
        await interaction.followup.send(response_message)

    @power_load.on_autocomplete("cogname")
    @power_unload.on_autocomplete("cogname")
    @power_reload.on_autocomplete("cogname")
    async def list_cogs(self, interaction: Interaction, cogname: str):
        if not cogname:
            # send the full autocomplete list
            await interaction.response.send_autocomplete(self.all_cogs)
            return
        # send a list of nearest matches from the list of cogs
        get_near_cog = [c for c in self.all_cogs if c.lower().startswith(cogname.lower())]
        await interaction.response.send_autocomplete(get_near_cog)

    # ── Delete Server Data ────────────────────────────────────────────

    @nextcord.slash_command(
        name="powercord",
        description="Powercord management commands.",
        default_member_permissions=nextcord.Permissions(administrator=True),
    )
    async def powercord(self, interaction: Interaction) -> None:
        """Parent group for Powercord admin commands."""

    @powercord.subcommand(
        name="delete_server_data",
        description="Delete all data stored by an extension for this server.",
    )
    async def delete_server_data(
        self,
        interaction: Interaction,
        extension: str = SlashOption(
            name="extension",
            description="Extension whose data should be deleted.",
        ),
    ) -> None:
        """Slash command to purge an extension's guild-specific data."""
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        # Validate the extension supports deletion
        deletable = get_deletable_extensions()
        if extension not in deletable:
            await interaction.response.send_message(
                f"Extension **{extension}** does not support data deletion.",
                ephemeral=True,
            )
            return

        # Show confirmation prompt
        view = ConfirmDeleteView()
        await interaction.response.send_message(
            f"⚠️ **This will permanently delete all {extension.capitalize()} data "
            f"for this server.** This cannot be undone.\n\nAre you sure?",
            view=view,
            ephemeral=True,
        )
        await view.wait()

        if view.value is None:
            await interaction.edit_original_message(content="Command timed out.", view=None)
        elif view.value is False:
            await interaction.edit_original_message(content="Data deletion cancelled.", view=None)
        else:
            # Execute the delete
            run_hook(extension, "delete_guild_data", guild_id=interaction.guild.id)
            await interaction.edit_original_message(
                content=f"✅ All **{extension.capitalize()}** data for this server has been deleted.",
                view=None,
            )

    @delete_server_data.on_autocomplete("extension")
    async def autocomplete_deletable_extensions(self, interaction: Interaction, extension: str) -> None:
        """Autocomplete handler — only lists extensions that support data deletion."""
        deletable = get_deletable_extensions()
        if not extension:
            await interaction.response.send_autocomplete(deletable)
            return
        matches = [e for e in deletable if e.lower().startswith(extension.lower())]
        await interaction.response.send_autocomplete(matches)

    # ── API Access Management ────────────────────────────────────────────

    def _get_api_scopes(self) -> list[str]:
        inspector = GadgetInspector()
        extensions = list(inspector.inspect_extensions().keys())
        return ["global", "default"] + extensions

    @powercord.subcommand(
        name="api_access_grant",
        description="Grant API access (a specific scope) to a Discord role.",
    )
    async def api_access_grant(
        self,
        interaction: Interaction,
        role: nextcord.Role = SlashOption(name="role", description="The Discord role to grant access to."),  # noqa: B008
        scope: str = SlashOption(name="scope", description="The API scope to grant."),  # noqa: B008
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        valid_scopes = self._get_api_scopes()
        if scope not in valid_scopes:
            await interaction.response.send_message(f"Invalid scope: `{scope}`.", ephemeral=True)
            return

        engine = init_connection_engine()
        with Session(engine) as session:
            # Check if it already exists
            stmt = select(ApiAccessRole).where(
                ApiAccessRole.guild_id == interaction.guild.id,
                ApiAccessRole.role_id == role.id,
                ApiAccessRole.extension_name == scope,
            )
            existing = session.exec(stmt).first()
            if existing:
                await interaction.response.send_message(
                    f"Role {role.mention} already has the `{scope}` API scope.", ephemeral=True
                )
                return

            new_mapping = ApiAccessRole(guild_id=interaction.guild.id, role_id=role.id, extension_name=scope)
            session.add(new_mapping)
            session.commit()

        await interaction.response.send_message(f"✅ Granted `{scope}` API scope to {role.mention}.", ephemeral=True)

    @api_access_grant.on_autocomplete("scope")
    async def autocomplete_grant_scopes(self, interaction: Interaction, scope: str) -> None:
        scopes = self._get_api_scopes()
        if not scope:
            await interaction.response.send_autocomplete(scopes[:25])
            return
        matches = [s for s in scopes if s.lower().startswith(scope.lower())]
        await interaction.response.send_autocomplete(matches[:25])

    @powercord.subcommand(
        name="api_access_revoke",
        description="Revoke API access (a specific scope) from a Discord role.",
    )
    async def api_access_revoke(
        self,
        interaction: Interaction,
        role: nextcord.Role = SlashOption(name="role", description="The Discord role to revoke access from."),  # noqa: B008
        scope: str = SlashOption(name="scope", description="The API scope to revoke."),  # noqa: B008
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        valid_scopes = self._get_api_scopes()
        if scope not in valid_scopes:
            await interaction.response.send_message(f"Invalid scope: `{scope}`.", ephemeral=True)
            return

        engine = init_connection_engine()
        with Session(engine) as session:
            stmt = select(ApiAccessRole).where(
                ApiAccessRole.guild_id == interaction.guild.id,
                ApiAccessRole.role_id == role.id,
                ApiAccessRole.extension_name == scope,
            )
            existing = session.exec(stmt).first()
            if not existing:
                await interaction.response.send_message(
                    f"Role {role.mention} does not have the `{scope}` API scope.", ephemeral=True
                )
                return

            session.delete(existing)
            session.commit()

        await interaction.response.send_message(f"✅ Revoked `{scope}` API scope from {role.mention}.", ephemeral=True)

    @api_access_revoke.on_autocomplete("scope")
    async def autocomplete_revoke_scopes(self, interaction: Interaction, scope: str) -> None:
        scopes = self._get_api_scopes()
        if not scope:
            await interaction.response.send_autocomplete(scopes[:25])
            return
        matches = [s for s in scopes if s.lower().startswith(scope.lower())]
        await interaction.response.send_autocomplete(matches[:25])

    @powercord.subcommand(
        name="api_access_list",
        description="List all API access roles configured for this server.",
    )
    async def api_access_list(self, interaction: Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        engine = init_connection_engine()
        with Session(engine) as session:
            stmt = select(ApiAccessRole).where(ApiAccessRole.guild_id == interaction.guild.id)
            mappings = session.exec(stmt).all()

        if not mappings:
            await interaction.response.send_message("No API access roles configured for this server.", ephemeral=True)
            return

        # Group by role_id
        role_scopes: dict[int, list[str]] = {}
        for mapping in mappings:
            if mapping.role_id not in role_scopes:
                role_scopes[mapping.role_id] = []
            role_scopes[mapping.role_id].append(mapping.extension_name)

        embed = nextcord.Embed(title="API Access Roles", color=nextcord.Color.blue())
        for role_id, scopes in role_scopes.items():
            role_mention = f"<@&{role_id}>"
            embed.add_field(name="Role", value=role_mention, inline=False)
            embed.add_field(name="Scopes", value=" ".join(f"`{s}`" for s in scopes), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


def setup(bot: commands.Bot):
    import typing

    bot.add_cog(AppPowerLoader(typing.cast("Bot", bot)))
