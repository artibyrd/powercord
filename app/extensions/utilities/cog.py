import json
import logging

import nextcord
from nextcord.ext import commands
from sqlmodel import Session, col, delete

from app.common.alchemy import init_connection_engine
from app.db.models import DiscordChannel, DiscordRole

engine = init_connection_engine()


class UtilitiesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def serialize_overwrites(self, channel: nextcord.abc.GuildChannel) -> str:
        """Serializes permission overwrites into a JSON string."""
        serialized = {}
        for target, overwrite in channel.overwrites.items():
            allow, deny = overwrite.pair()
            target_type = "role" if isinstance(target, nextcord.Role) else "member"
            serialized[str(target.id)] = {
                "type": target_type,
                "name": target.name,  # Store name for easier UI rendering without fetch
                "allow": allow.value,
                "deny": deny.value,
            }
        return json.dumps(serialized)

    async def audit_guild(self, guild: nextcord.Guild):
        """Audits guild roles and channels and stores them in the database.

        This method captures a snapshot of the server's current state:
        1. Iterates through all roles and saves their permissions, colors, and hierarchical position.
        2. Iterates through all channels, saving their types and serializing their permission overwrites.
        3. Wipes the existing database records for this guild and inserts the fresh data.
        """
        logging.info(f"Starting audit for guild: {guild.name} ({guild.id})")

        # 1. Collect Role Data
        roles_data = []
        for role in guild.roles:
            roles_data.append(
                DiscordRole(
                    id=role.id,
                    guild_id=guild.id,
                    name=role.name,
                    permissions=role.permissions.value,
                    position=role.position,
                    color=role.color.value,
                    is_hoisted=role.hoist,
                    is_managed=role.managed,
                    is_mentionable=role.mentionable,
                )
            )

        # 2. Collect Channel Data
        channels_data = []
        for channel in guild.channels:
            # Determine channel type string
            ch_type = str(channel.type)

            parent_id = channel.category_id if hasattr(channel, "category_id") else None

            channels_data.append(
                DiscordChannel(
                    id=channel.id,
                    guild_id=guild.id,
                    parent_id=parent_id,
                    name=channel.name,
                    type=ch_type,
                    position=channel.position,
                    overwrites=self.serialize_overwrites(channel),
                )
            )

        # Partition channels
        categories = [c for c in channels_data if c.parent_id is None]
        children = [c for c in channels_data if c.parent_id is not None]

        # 3. Update Database
        try:
            with Session(engine) as session:
                # Remove old data for this guild
                session.exec(delete(DiscordRole).where(col(DiscordRole.guild_id) == guild.id))
                session.exec(delete(DiscordChannel).where(col(DiscordChannel.guild_id) == guild.id))

                # Add roles and categories (parents) first
                session.add_all(roles_data)
                session.add_all(categories)
                session.commit()  # Commit to ensure parents are visible for FK checks

                # Add children
                for child in children:
                    # Re-attach to session if needed (objects might be detached after commit if expire_on_commit=True,
                    # but we are adding new objects so it should be fine)
                    session.add(child)
                session.commit()

            logging.info(
                f"Audit complete for guild {guild.name}. Synced {len(roles_data)} roles and {len(channels_data)} channels."
            )
        except Exception as e:
            logging.error(f"Failed to save audit data for guild {guild.name}: {e}")
            raise e

    def verify_bot_permissions(self, guild: nextcord.Guild) -> list[str]:
        """Checks if the bot has necessary permissions."""
        me = guild.me
        missing = []
        if not me.guild_permissions.manage_roles and not me.guild_permissions.administrator:
            missing.append("Manage Roles")
        if not me.guild_permissions.manage_channels and not me.guild_permissions.administrator:
            missing.append("Manage Channels")
        return missing

    @commands.command(name="audit")
    @commands.has_permissions(administrator=True)  # type: ignore[type-var]
    async def manual_audit(self, ctx: commands.Context):
        """Manually triggers the server permission auditor."""
        guild = ctx.guild
        if guild is None:
            await ctx.send("❌ This command must be used in a server.")
            return

        missing = self.verify_bot_permissions(guild)
        if missing:
            await ctx.send(f"❌ Bot is missing permissions: {', '.join(missing)}")
            return

        await ctx.send("Starting server permission audit...")
        async with ctx.typing():
            try:
                await self.audit_guild(guild)
                await ctx.send("✅ Audit complete! Dashboard updated.")
            except Exception as e:
                await ctx.send(f"❌ Audit failed: {e}")

    @nextcord.slash_command(
        name="audit",
        description="Triggers the server permission auditor.",
        default_member_permissions=nextcord.Permissions(administrator=True),
    )
    async def slash_audit(self, interaction: nextcord.Interaction):
        """Slash command to trigger the audit."""
        if not interaction.guild or not isinstance(interaction.user, nextcord.Member):
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        # Defer response since audit might take a moment
        await interaction.response.defer()

        # Check User Permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ You need Administrator permissions to use this command.")
            return

        guild = interaction.guild
        # Check Bot Permissions
        missing = self.verify_bot_permissions(guild)
        if missing:
            await interaction.followup.send(f"❌ Bot is missing permissions: {', '.join(missing)}")
            return

        try:
            await self.audit_guild(guild)
            await interaction.followup.send("✅ Audit complete! Dashboard updated.")
        except Exception as e:
            await interaction.followup.send(f"❌ Audit failed: {e}")

    # Optionally, we could add a listener to update on changes,
    # but the request said "this data changes fairly infrequently" and suggested a refresh mechanism.
    # We'll stick to manual trigger for now, or maybe a periodic task if requested later.


def setup(bot: commands.Bot):
    bot.add_cog(UtilitiesCog(bot))
