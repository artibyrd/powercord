"""Example extension cog facade, basic commands, background tasks, and context overrides.

This module houses the primary ExamplesCog and registers all sub-cogs for the example
extension, along with AST-inspected CogContexts and CogPersists.
"""

import asyncio
import random
from typing import Union

import nextcord
from nextcord.ext import commands, tasks

from app.common.guild_cog import GuildAwareCog

from .app_commands_cog import AppCommandsCog
from .converters import ChannelOrMemberConverter
from .events_cog import EventsCog
from .modals import Pet
from .secret_cog import SecretCog
from .todo_cog import TodoCog
from .views import (
    Confirm,
    Counter,
    Dropdown,
    DropdownView,
    EphemeralCounter,
    Google,
    TicTacToe,
    TicTacToeButton,
    send_to_webhook,
)
from .views_cog import ViewsCog


# === BOT STARTUP OVERRIDE CLASSES === #
# Some bot features (custom contexts, persistent modals/views) require
# overriding base Bot classes before the bot starts.
# Detected via AST inspection in GadgetInspector.inspect_cogs().
class CogContexts(commands.Context):
    """Custom context methods prefixed with cc_."""

    async def cc_tick(self, value):
        emoji = "\N{WHITE HEAVY CHECK MARK}" if value else "\N{CROSS MARK}"
        try:
            await self.message.add_reaction(emoji)
        except nextcord.HTTPException:
            pass


class CogPersists:
    """Persistent views and modals detected via AST inspection."""

    class PersistentView(nextcord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @nextcord.ui.button(
            label="Green",
            style=nextcord.ButtonStyle.green,
            custom_id="persistent_view:green",
        )
        async def green(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
            await interaction.response.send_message("This is green.", ephemeral=True)

        @nextcord.ui.button(label="Red", style=nextcord.ButtonStyle.red, custom_id="persistent_view:red")
        async def red(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
            await interaction.response.send_message("This is red.", ephemeral=True)

        @nextcord.ui.button(
            label="Grey",
            style=nextcord.ButtonStyle.grey,
            custom_id="persistent_view:grey",
        )
        async def grey(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
            await interaction.response.send_message("This is grey.", ephemeral=True)

    class FeedbackModal(nextcord.ui.Modal):
        def __init__(self):
            super().__init__(
                title="Feedback",
                custom_id="persistent_modal:feedback",
                timeout=None,
            )

            self.discovered = nextcord.ui.TextInput(
                label="How did you discover the bot?",
                placeholder="e.g. Discord server, friend, etc.",
                required=False,
                style=nextcord.TextInputStyle.paragraph,
                custom_id="persistent_modal:discovered",
            )
            self.add_item(self.discovered)

            self.rating = nextcord.ui.TextInput(
                label="How would you rate the bot out of 10?",
                placeholder="10",
                max_length=2,
                custom_id="persistent_modal:rating",
            )
            self.add_item(self.rating)

            self.improve = nextcord.ui.TextInput(
                label="How could the bot improve?",
                placeholder="e.g. add more features, improve the UI, etc.",
                style=nextcord.TextInputStyle.paragraph,
                required=False,
                custom_id="persistent_modal:improve",
            )
            self.add_item(self.improve)

        async def callback(self, interaction: nextcord.Interaction):
            await interaction.send(
                f"Feedback from {interaction.user.mention}:\n"
                f"Rating: {self.rating.value}\n"
                f"Where they discovered the bot: {self.discovered.value}\n"
                f"How could the bot improve: {self.improve.value}\n"
            )


# === MAIN EXAMPLE COG CLASS === #
class ExamplesCog(GuildAwareCog):
    """Primary example cog managing basic commands, background tasks, and converters."""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.channel_id = 256838648870207498
        self.bg_counter = 0
        self.asyncio_task = None

    def start_counters(self):
        """Starts background counter tasks (called by internal_server API)."""
        if not self.bg_counter_task.is_running():
            self.bg_counter_task.start()

        if not self.asyncio_task or self.asyncio_task.done():
            self.asyncio_task = self.bot.loop.create_task(self.asyncio_counter_task())

    def stop_counters(self):
        """Stops background counter tasks (called by internal_server API)."""
        if self.bg_counter_task.is_running():
            self.bg_counter_task.cancel()

        if self.asyncio_task and not self.asyncio_task.done():
            self.asyncio_task.cancel()

    # == BASIC EXAMPLES == #
    @commands.command()
    async def helloworld(self, ctx):
        await ctx.reply("Hello, world!")

    @commands.command()
    async def headsortails(self, ctx, answer):
        if random.choice(["heads", "tails"]) == answer:
            await ctx.reply("Congratulations!")
        else:
            await ctx.reply("Sorry, you lost.")

    @commands.command()
    async def add(self, ctx, left: int, right: int):
        await ctx.send(left + right)

    @commands.command()
    async def roll(self, ctx, dice: str):
        try:
            rolls, limit = map(int, dice.split("d"))
        except Exception:
            await ctx.send("Format has to be in NdN!")
            return
        result = ", ".join(str(random.randint(1, limit)) for r in range(rolls))
        await ctx.send(result)

    @commands.command(description="Randomly select between multiple choices")
    async def choose(self, ctx, *choices: str):
        await ctx.send(random.choice(choices))

    @commands.command()
    async def repeat(self, ctx, times: int, content="repeating..."):
        for _ in range(times):
            await ctx.send(content)

    @commands.command()
    async def joined(self, ctx, member: nextcord.Member):
        await ctx.send(f"{member.name} joined in {member.joined_at}")

    @commands.group()
    async def cool(self, ctx):
        """Says if a user is cool."""
        if ctx.invoked_subcommand is None:
            await ctx.send(f"No, {ctx.subcommand_passed} is not cool")

    @cool.command(name="bot")
    async def _bot(self, ctx):
        """Is the bot cool?"""
        await ctx.send("Yes, the bot is cool.")

    @commands.command()
    async def guessing_game(self, ctx):
        await ctx.send("Guess a number between 1 and 10.")

        def is_correct(m):
            return m.author == ctx.author and m.content.isdigit()

        answer = random.randint(1, 10)
        try:
            guess = await self.bot.wait_for("message", check=is_correct, timeout=5.0)
        except asyncio.TimeoutError:
            return await ctx.send(f"Sorry, you took too long it was {answer}.")

        if int(guess.content) == answer:
            await ctx.send("You are right!")
        else:
            await ctx.send(f"Oops. It is actually {answer}.")

    # == BACKGROUND TASKS == #
    async def asyncio_counter_task(self):
        await self.bot.wait_until_ready()
        counter = 0
        channel = self.bot.get_channel(self.channel_id)
        while not self.bot.is_closed() and counter < 3:
            counter += 1
            await channel.send(f"Asyncio Counter (demonstrates `asyncio.create_task`): {counter}")
            await asyncio.sleep(5)

    @tasks.loop(seconds=3.0, count=3)
    async def bg_counter_task(self):
        channel = self.bot.get_channel(self.channel_id)
        self.bg_counter += 1
        await channel.send(f"Background Counter (demonstrates `tasks.loop`): {self.bg_counter}")

    @bg_counter_task.after_loop
    async def after_bg_counter_task(self):
        channel = self.bot.get_channel(self.channel_id)
        await channel.send("Background counter completed!")

    @bg_counter_task.before_loop
    async def before_bg_counter_task(self):
        await self.bot.wait_until_ready()

    def cog_unload(self) -> None:
        self.bg_counter_task.cancel()
        return super().cog_unload()

    # == CONVERTERS == #
    @commands.command()
    async def userinfo(self, ctx, user: nextcord.User):
        user_id = user.id
        username = user.name
        avatar = user.avatar.url
        await ctx.send(f"User found: {user_id} -- {username}\n{avatar}")

    @userinfo.error
    async def userinfo_error(self, ctx, error: commands.CommandError):
        if isinstance(error, commands.BadArgument):
            return await ctx.send("Couldn't find that user.")

    @commands.command()
    async def notify(self, ctx, target: ChannelOrMemberConverter):
        await target.send(f"Hello, {target.name}!")

    @commands.command()
    async def ignore(self, ctx, target: Union[nextcord.Member, nextcord.TextChannel]):
        if isinstance(target, nextcord.Member):
            await ctx.send(f"Member found: {target.mention}, adding them to the ignore list.")
        elif isinstance(target, nextcord.TextChannel):
            await ctx.send(f"Channel found: {target.mention}, adding it to the ignore list.")

    @commands.command()
    async def multiply(self, ctx, number: int, maybe: bool):
        if maybe is True:
            return await ctx.send(number * 2)
        await ctx.send(number * 5)

    # == CUSTOM CONTEXT == #
    @commands.command()
    async def guess(self, ctx, number: int):
        """Guess a random number from 1 to 6."""
        value = random.randint(1, 6)
        await ctx.cc_tick(ctx, number == value)


def setup(bot: commands.Bot):
    """Extension entry point: registers all example sub-cogs."""
    bot.add_cog(ExamplesCog(bot))
    bot.add_cog(EventsCog(bot))
    bot.add_cog(SecretCog(bot))
    bot.add_cog(AppCommandsCog(bot))
    bot.add_cog(ViewsCog(bot))
    bot.add_cog(TodoCog(bot))


__all__ = [
    "AppCommandsCog",
    "ChannelOrMemberConverter",
    "CogContexts",
    "CogPersists",
    "Confirm",
    "Counter",
    "Dropdown",
    "DropdownView",
    "EphemeralCounter",
    "EventsCog",
    "ExamplesCog",
    "Google",
    "Pet",
    "SecretCog",
    "TicTacToe",
    "TicTacToeButton",
    "TodoCog",
    "ViewsCog",
    "send_to_webhook",
    "setup",
]
