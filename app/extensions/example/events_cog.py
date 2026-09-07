"""Example event listeners and reaction role management."""

import asyncio

import nextcord
from nextcord.ext import commands

from app.common.guild_cog import GuildAwareCog


class EventsCog(GuildAwareCog):
    """Cog demonstrating event listeners, reaction roles, and self-modifying messages."""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.role_message_id = 970656589432356884
        self.emoji_to_role = {
            nextcord.PartialEmoji(name="🔴"): 970656160724164669,
            nextcord.PartialEmoji(name="🟡"): 970656256874405929,
            nextcord.PartialEmoji(name="green", id=970660584657944626): 970656941934252032,
        }

    # Listen for deleted messages
    @commands.Cog.listener()
    async def on_message_delete(self, message: nextcord.Message):
        if message.guild and not self.guild_enabled(message.guild.id):
            return
        msg = f"{message.author} has deleted the message: {message.content}"
        await message.channel.send(msg)

    # Self destructing messages to trigger on_message_delete listener
    @commands.command()
    async def deleteme(self, ctx):
        msg = await ctx.send("I will delete myself now...")
        await msg.delete()
        await ctx.send("Goodbye in 3 seconds...", delete_after=3.0)

    # Listen for edited messages
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.guild and not self.guild_enabled(before.guild.id):
            return
        msg = f"**{before.author}** edited their message:\n{before.content} -> {after.content}"
        await before.channel.send(msg)

    # Self editing message to trigger on_message_edit listener
    @commands.command()
    async def editme(self, ctx):
        msg = await ctx.send("69")
        await asyncio.sleep(3.0)
        await msg.edit(content="420")

    # Welcome new member
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not self.guild_enabled(member.guild.id):
            return
        guild = member.guild
        if guild.system_channel is not None:
            to_send = f"Welcome {member.mention} to {guild.name}!"
            await guild.system_channel.send(to_send)

    # Add roles on reaction
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: nextcord.RawReactionActionEvent):
        """Gives a role based on a reaction emoji."""
        if payload.guild_id and not self.guild_enabled(payload.guild_id):
            return
        if payload.message_id != self.role_message_id:
            return

        guild = self.get_guild(payload.guild_id)
        if guild is None:
            return

        try:
            role_id = self.emoji_to_role[payload.emoji]
        except KeyError:
            return

        role = guild.get_role(role_id)
        if role is None:
            return

        try:
            await payload.member.add_roles(role)
        except nextcord.HTTPException:
            pass

    # Remove roles on reaction remove
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: nextcord.RawReactionActionEvent):
        """Removes a role based on a reaction emoji."""
        if payload.guild_id and not self.guild_enabled(payload.guild_id):
            return
        if payload.message_id != self.role_message_id:
            return

        guild = self.get_guild(payload.guild_id)
        if guild is None:
            return

        try:
            role_id = self.emoji_to_role[payload.emoji]
        except KeyError:
            return

        role = guild.get_role(role_id)
        if role is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            return

        try:
            await member.remove_roles(role)
        except nextcord.HTTPException:
            pass
