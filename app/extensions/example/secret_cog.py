"""Example secret commands and permission overwrite helpers."""

import typing

import nextcord
from nextcord.ext import commands

from app.common.guild_cog import GuildAwareCog


class SecretCog(GuildAwareCog):
    """Cog demonstrating channel creation with permission overwrites."""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    def create_overwrites(self, ctx, *objects):
        """Helper function that creates the overwrites for voice/text channels."""
        overwrites = {obj: nextcord.PermissionOverwrite(view_channel=True) for obj in objects}
        overwrites.setdefault(ctx.guild.default_role, nextcord.PermissionOverwrite(view_channel=False))
        overwrites[ctx.guild.me] = nextcord.PermissionOverwrite(view_channel=True)
        return overwrites

    @commands.group(hidden=True)
    async def secret(self, ctx):
        """What is this "secret" you speak of?"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Shh!", delete_after=5)

    @secret.command()
    @commands.guild_only()
    async def text(self, ctx, name: str, *objects: typing.Union[nextcord.Role, nextcord.Member]):
        """Creates a text channel with a given name visible only to specified objects."""
        overwrites = self.create_overwrites(ctx, *objects)
        await ctx.guild.create_text_channel(
            name,
            overwrites=overwrites,
            topic="Top secret text channel. Any leakage of this channel may result in serious trouble.",
            reason="Very secret business.",
        )

    @secret.command()
    @commands.guild_only()
    async def voice(self, ctx, name: str, *objects: typing.Union[nextcord.Role, nextcord.Member]):
        """Creates a voice channel with a given name visible only to specified objects."""
        overwrites = self.create_overwrites(ctx, *objects)
        await ctx.guild.create_voice_channel(name, overwrites=overwrites, reason="Very secret business.")

    @secret.command()
    @commands.guild_only()
    async def emoji(self, ctx, emoji: nextcord.PartialEmoji, *roles: nextcord.Role):
        """Clones a given emoji that only specified roles are allowed to use."""
        emoji_bytes = await emoji.read()
        await ctx.guild.create_custom_emoji(
            name=emoji.name,
            image=emoji_bytes,
            roles=roles,
            reason="Very secret business.",
        )
