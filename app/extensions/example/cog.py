import asyncio
import os
import random
import typing
from typing import List, Union
from urllib.parse import quote_plus

### === WEBHOOK EXAMPLE === ###
import aiohttp
import nextcord
from nextcord import Interaction, Member, Message, SlashOption
from nextcord.ext import commands, tasks
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.common.guild_cog import GuildAwareCog

from .blueprint import TodoItem

WEBHOOK_URL = os.environ.get("POWERCORD_EXAMPLE_WEBHOOK_URL", "")


async def send_to_webhook(url, content):
    # Create a new HTTP session and use it to create webhook object
    async with aiohttp.ClientSession() as session:
        webhook = nextcord.Webhook.from_url(url, session=session)
        await webhook.send(content)


if __name__ == "__main__":
    # You can test the webhook by running this file directly
    asyncio.run(send_to_webhook(f"{WEBHOOK_URL}", "Hello, world!"))


### === MODAL EXAMPLE CLASSES === ###
# Example basic modal class
class Pet(nextcord.ui.Modal):
    def __init__(self):
        super().__init__(
            "Your pet",
            timeout=5 * 60,  # 5 minutes
        )

        self.name = nextcord.ui.TextInput(
            label="Your pet's name",
            min_length=2,
            max_length=50,
        )
        self.add_item(self.name)

        self.description = nextcord.ui.TextInput(
            label="Description",
            style=nextcord.TextInputStyle.paragraph,
            placeholder="Information that can help us recognise your pet",
            required=False,
            max_length=1800,
        )
        self.add_item(self.description)

    async def callback(self, interaction: nextcord.Interaction) -> None:
        response = f"{interaction.user.mention}'s favourite pet's name is {self.name.value}."
        if self.description.value != "":
            response += f"\nTheir pet can be recognized by this information:\n{self.description.value}"
        await interaction.send(response)


# See BOT STARTUP OVERRIDE CLASSES below
# for example using persistent modals in cogs


### === VIEW EXAMPLE CLASSES === ###
# Example simple search button class
class Google(nextcord.ui.View):
    def __init__(self, query: str):
        super().__init__()
        query = quote_plus(query)
        url = f"https://www.google.com/search?q={query}"
        # Link buttons cannot be made with the decorator, we must make them here!
        self.add_item(nextcord.ui.Button(label="Click Here", url=url))


# Example comfirmation view class
class Confirm(nextcord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    @nextcord.ui.button(label="Confirm", style=nextcord.ButtonStyle.green)
    async def confirm(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message("Confirming", ephemeral=True)
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @nextcord.ui.button(label="Cancel", style=nextcord.ButtonStyle.grey)
    async def cancel(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message("Cancelling", ephemeral=True)
        self.value = False
        self.stop()


# Example counter button view class
class Counter(nextcord.ui.View):
    # When pressed, this increments the number displayed until it hits 5.
    # When it hits 5, the counter button is disabled and it turns green.
    # note: The name of the function does not matter to the library
    @nextcord.ui.button(label="0", style=nextcord.ButtonStyle.red)
    async def count(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        number = int(button.label) if button.label else 0
        if number + 1 >= 5:
            button.style = nextcord.ButtonStyle.green
            button.disabled = True
        button.label = str(number + 1)
        # Make sure to update the message with our updated selves
        await interaction.response.edit_message(view=self)


# Example ephemeral counter button view class
class EphemeralCounter(nextcord.ui.View):
    # When this button is pressed, it will respond with a Counter view that will
    # give the button presser their own personal button they can press 5 times.
    @nextcord.ui.button(label="Click", style=nextcord.ButtonStyle.blurple)
    async def receive(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        # ephemeral=True makes the message hidden from everyone except the button presser
        await interaction.response.send_message("Enjoy!", view=Counter(), ephemeral=True)


# Example dropdown select view classes
class Dropdown(nextcord.ui.Select):
    def __init__(self):
        # Set the options that will be presented inside the dropdown
        options = [
            nextcord.SelectOption(label="Red", description="Your favourite colour is red", emoji="🟥"),
            nextcord.SelectOption(label="Green", description="Your favourite colour is green", emoji="🟩"),
            nextcord.SelectOption(label="Blue", description="Your favourite colour is blue", emoji="🟦"),
        ]
        # The placeholder is what will be shown when no option is chosen
        # The min and max values indicate we can only pick one of the three options
        # The options parameter defines the dropdown options. We defined this above
        super().__init__(
            placeholder="Choose your favourite colour...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: nextcord.Interaction):
        # Use the interaction object to send a response message containing
        # the user's favourite colour or choice. The self object refers to the
        # Select object, and the values attribute gets a list of the user's
        # selected options. We only want the first one.
        await interaction.response.send_message(f"Your favourite colour is {self.values[0]}")


class DropdownView(nextcord.ui.View):
    def __init__(self):
        super().__init__()

        # Adds the dropdown to our view object.
        self.add_item(Dropdown())


# See BOT STARTUP OVERRIDE CLASSES below
# for examples using persistent views in cogs


### === ADVANCED VIEW DEMO CLASSES === ###
# TicTacToe game logic class
class TicTacToeButton(nextcord.ui.Button["TicTacToe"]):
    def __init__(self, x: int, y: int):
        # A label is required, but we don't need one so a zero-width space is used
        # The row parameter tells the View which row to place the button under.
        # A View can only contain up to 5 rows -- each row can only have 5 buttons.
        # Since a Tic Tac Toe grid is 3x3 that means we have 3 rows and 3 columns.
        super().__init__(style=nextcord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    # This function is called whenever this particular button is pressed
    # This is part of the "meat" of the game logic
    async def callback(self, interaction: nextcord.Interaction):
        assert self.view is not None
        view: TicTacToe = self.view
        state = view.board[self.y][self.x]
        if state in (view.X, view.O):
            return

        if view.current_player == view.X:
            self.style = nextcord.ButtonStyle.danger
            self.label = "X"
            self.disabled = True
            view.board[self.y][self.x] = view.X
            view.current_player = view.O
            content = "It is now O's turn"
        else:
            self.style = nextcord.ButtonStyle.success
            self.label = "O"
            self.disabled = True
            view.board[self.y][self.x] = view.O
            view.current_player = view.X
            content = "It is now X's turn"

        winner = view.check_board_winner()
        if winner is not None:
            if winner == view.X:
                content = "X won!"
            elif winner == view.O:
                content = "O won!"
            else:
                content = "It's a tie!"

            for child in view.children:
                child.disabled = True

            view.stop()

        await interaction.response.edit_message(content=content, view=view)


# TicTacToe board View class
class TicTacToe(nextcord.ui.View):
    # This tells the IDE or linter that all our children will be TicTacToeButtons
    # This is not required
    children: List[TicTacToeButton]
    X = -1
    O = 1
    Tie = 2

    def __init__(self):
        super().__init__()
        self.current_player = self.X
        self.board = [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ]

        # Our board is made up of 3 by 3 TicTacToeButtons
        # The TicTacToeButton maintains the callbacks and helps steer
        # the actual game.
        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))

    # This method checks for the board winner -- it is used by the TicTacToeButton
    def check_board_winner(self):
        for across in self.board:
            value = sum(across)
            if value == 3:
                return self.O
            elif value == -3:
                return self.X

        # Check vertical
        for line in range(3):
            value = self.board[0][line] + self.board[1][line] + self.board[2][line]
            if value == 3:
                return self.O
            elif value == -3:
                return self.X

        # Check diagonals
        diag = self.board[0][2] + self.board[1][1] + self.board[2][0]
        if diag == 3:
            return self.O
        elif diag == -3:
            return self.X

        diag = self.board[0][0] + self.board[1][1] + self.board[2][2]
        if diag == 3:
            return self.O
        elif diag == -3:
            return self.X

        # If we're here, we need to check if a tie was made
        if all(i != 0 for row in self.board for i in row):
            return self.Tie

        return None


### === OTHER EXAMPLE CLASSES === ###
# Custom converter class
class ChannelOrMemberConverter(commands.Converter):
    async def convert(self, ctx, argument: str):
        # In this example we have made a custom converter.
        # This checks if an input is convertible to a
        # `nextcord.Member` or `nextcord.TextChannel` instance from the
        # input the user has given us using the pre-existing converters
        # that the library provides.

        member_converter = commands.MemberConverter()
        try:
            # Try and convert to a Member instance.
            # If this fails, then an exception is raised.
            # Otherwise, we just return the converted member value.
            member = await member_converter.convert(ctx, argument)
        except commands.MemberNotFound:
            pass
        else:
            return member

        # Do the same for TextChannel...
        textchannel_converter = commands.TextChannelConverter()
        try:
            channel = await textchannel_converter.convert(ctx, argument)
        except commands.ChannelNotFound:
            pass
        else:
            return channel

        # If the value could not be converted we can raise an error
        # so our error handlers can deal with it in one place.
        # The error has to be CommandError derived, so BadArgument works fine here.
        raise commands.BadArgument(f'No Member or TextChannel could be converted from "{argument}"')


### === BOT STARTUP OVERRIDE CLASSES === ###
# Some bot features (custom contexts, persistent modals/views)
# require overriding base Bot classes before the bot is started.
# See bottom of cogs/powerloader/cog_gobbler.py for more details.
## == NOTICE == ##
# Using these features means the cog must be included when the bot
# initially starts, and cannot be hot loaded after the bot has started!


class CogContexts(commands.Context):
    # Functions in a cog's CogContexts class prefixed with cc_ will be registered in
    # __init__.py and added to the main commands.Context class override when the bot starts.

    async def cc_tick(self, value):
        # reacts to the message with an emoji
        # depending on whether value is True or False
        # if its True, it'll add a green check mark
        # otherwise, it'll add a red cross mark
        emoji = "\N{WHITE HEAVY CHECK MARK}" if value else "\N{CROSS MARK}"
        try:
            # this will react to the command author's message
            await self.message.add_reaction(emoji)
        except nextcord.HTTPException:
            # sometimes errors occur during this, for example
            # maybe you don't have permission to do that
            # we don't mind, so we can just ignore them
            pass


class CogPersists:
    # Classes found in a cog's CogPersists class will be detected in __init__.py
    # and registered in the main Bot class as a persistent view/modal before the bot starts,
    # based on the inherited class type used here (nextcord.ui.View or nexcord.ui.Modal).

    # Example persistent view
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

    # Example persistent modal
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


### === MAIN EXAMPLE COG CLASS === ###
# ==> Example Cog containing all of our actual demo commands
class ExamplesCog(GuildAwareCog):
    # Make sure to change IDs in __init__ to match your server!
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.channel_id = 256838648870207498  # ID of the default channel to use for sending messages.
        # Reaction roles settings
        self.role_message_id = 970656589432356884  # ID of the message that we check for reactions to add/remove a role.
        self.emoji_to_role = {
            nextcord.PartialEmoji(name="🔴"): 970656160724164669,  # ID of the role associated with unicode emoji '🔴'.
            nextcord.PartialEmoji(name="🟡"): 970656256874405929,  # ID of the role associated with unicode emoji '🟡'.
            nextcord.PartialEmoji(
                name="green", id=970660584657944626
            ): 970656941934252032,  # ID of the role associated with a partial emoji's ID.
        }
        # Background tasks
        self.bg_counter = 0
        self.asyncio_task = None
        # The following lines are commented out to prevent the example tasks from running automatically on bot startup.
        # They can be manually started/stopped via the Admin Dashboard.
        # self.bg_counter_task.start()
        # self.asyncio_task = self.bot.loop.create_task(self.asyncio_counter_task())

    def start_counters(self):
        if not self.bg_counter_task.is_running():
            self.bg_counter_task.start()

        if not self.asyncio_task or self.asyncio_task.done():
            self.asyncio_task = self.bot.loop.create_task(self.asyncio_counter_task())

    def stop_counters(self):
        if self.bg_counter_task.is_running():
            self.bg_counter_task.cancel()

        if self.asyncio_task and not self.asyncio_task.done():
            self.asyncio_task.cancel()

    ### === BASIC EXAMPLES === ###
    # Hello, world!
    @commands.command()
    async def helloworld(self, ctx):
        await ctx.reply("Hello, world!")

    # Really simple heads or tails example
    @commands.command()
    async def headsortails(self, ctx, answer):
        if random.choice(["heads", "tails"]) == answer:
            await ctx.reply("Congratulations!")
        else:
            await ctx.reply("Sorry, you lost.")

    # Add two numbers together
    @commands.command()
    async def add(self, ctx, left: int, right: int):
        await ctx.send(left + right)

    # Rolls a dice in NdN format.
    @commands.command()
    async def roll(self, ctx, dice: str):
        try:
            rolls, limit = map(int, dice.split("d"))
        except Exception:
            await ctx.send("Format has to be in NdN!")
            return
        result = ", ".join(str(random.randint(1, limit)) for r in range(rolls))
        await ctx.send(result)

    # Random selection
    @commands.command(description="Randomly select between multiple choices")
    async def choose(self, ctx, *choices: str):
        await ctx.send(random.choice(choices))

    # Repeat a message some number of times
    @commands.command()
    async def repeat(self, ctx, times: int, content="repeating..."):
        for _ in range(times):
            await ctx.send(content)

    # Returns when a member joined
    @commands.command()
    async def joined(self, ctx, member: nextcord.Member):
        await ctx.send(f"{member.name} joined in {member.joined_at}")

    # Basic group commands example
    @commands.group()
    async def cool(self, ctx):
        """Says if a user is cool.
        In reality this just checks if a subcommand is being invoked.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(f"No, {ctx.subcommand_passed} is not cool")

    @cool.command(name="bot")
    async def _bot(self, ctx):
        """Is the bot cool?"""
        await ctx.send("Yes, the bot is cool.")

    # Guessing game
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

    # Listen for deleted messages
    @commands.Cog.listener()
    async def on_message_delete(self, message: nextcord.Message):
        # Skip if cog is disabled for this guild
        if message.guild and not self.guild_enabled(message.guild.id):
            return
        msg = f"{message.author} has deleted the message: {message.content}"
        await message.channel.send(msg)

    # Self destructing messages to trigger on_message_delete listener
    @commands.command()
    async def deleteme(self, ctx):
        msg = await ctx.send("I will delete myself now...")
        await msg.delete()
        # this also works
        await ctx.send("Goodbye in 3 seconds...", delete_after=3.0)

    # Listen for edited messages
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        # Skip if cog is disabled for this guild
        if before.guild and not self.guild_enabled(before.guild.id):
            return
        msg = f"**{before.author}** edited their message:\n{before.content} -> {after.content}"
        # This will throw nextcord.errors.HTTPException if msg > 2000 chars...
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
        # Skip if cog is disabled for this guild
        if not self.guild_enabled(member.guild.id):
            return
        guild = member.guild
        if guild.system_channel is not None:
            to_send = f"Welcome {member.mention} to {guild.name}!"
            await guild.system_channel.send(to_send)

    ## == REACTION ROLES == ##
    # Set message ID, role IDs, and emojis in __init__

    # Add roles
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: nextcord.RawReactionActionEvent):
        """Gives a role based on a reaction emoji."""
        # Skip if cog is disabled for this guild
        if payload.guild_id and not self.guild_enabled(payload.guild_id):
            return
        # Make sure that the message the user is reacting to is the one we care about.
        if payload.message_id != self.role_message_id:
            return

        guild = self.get_guild(payload.guild_id)
        if guild is None:
            # Check if we're still in the guild and it's cached.
            return

        try:
            role_id = self.emoji_to_role[payload.emoji]
        except KeyError:
            # If the emoji isn't the one we care about then exit as well.
            return

        role = guild.get_role(role_id)
        if role is None:
            # Make sure the role still exists and is valid.
            return

        try:
            # Finally, add the role.
            await payload.member.add_roles(role)
        except nextcord.HTTPException:
            # If we want to do something in case of errors we'd do it here.
            pass

    # Remove roles
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: nextcord.RawReactionActionEvent):
        """Removes a role based on a reaction emoji."""
        # Skip if cog is disabled for this guild
        if payload.guild_id and not self.guild_enabled(payload.guild_id):
            return
        # Make sure that the message the user is reacting to is the one we care about.
        if payload.message_id != self.role_message_id:
            return

        guild = self.get_guild(payload.guild_id)
        if guild is None:
            # Check if we're still in the guild and it's cached.
            return

        try:
            role_id = self.emoji_to_role[payload.emoji]
        except KeyError:
            # If the emoji isn't the one we care about then exit as well.
            return

        role = guild.get_role(role_id)
        if role is None:
            # Make sure the role still exists and is valid.
            return

        # The payload for `on_raw_reaction_remove` does not provide `.member`
        # so we must get the member ourselves from the payload's `.user_id`.
        member = guild.get_member(payload.user_id)
        if member is None:
            # Make sure the member still exists and is valid.
            return

        try:
            # Finally, remove the role.
            await member.remove_roles(role)
        except nextcord.HTTPException:
            # If we want to do something in case of errors we'd do it here.
            pass

    ## == "SECRET" COMMANDS == ##
    # Create role restricted channels or emojis

    @commands.group(hidden=True)
    async def secret(self, ctx):
        """What is this "secret" you speak of?"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Shh!", delete_after=5)

    def create_overwrites(self, ctx, *objects):
        """This is just a helper function that creates the overwrites for the
        voice/text channels.
        A `nextcord.PermissionOverwrite` allows you to determine the permissions
        of an object, whether it be a `nextcord.Role` or a `nextcord.Member`.
        In this case, the `view_channel` permission is being used to hide the channel
        from being viewed by whoever does not meet the criteria, thus creating a
        secret channel.
        """
        # a dict comprehension is being utilised here to set the same permission overwrites
        # for each `nextcord.Role` or `nextcord.Member`.
        overwrites = {obj: nextcord.PermissionOverwrite(view_channel=True) for obj in objects}
        # prevents the default role (@everyone) from viewing the channel
        # if it isn't already allowed to view the channel.
        overwrites.setdefault(ctx.guild.default_role, nextcord.PermissionOverwrite(view_channel=False))
        # makes sure the client is always allowed to view the channel.
        overwrites[ctx.guild.me] = nextcord.PermissionOverwrite(view_channel=True)
        return overwrites

    @secret.command()
    @commands.guild_only()
    async def text(self, ctx, name: str, *objects: typing.Union[nextcord.Role, nextcord.Member]):
        """This makes a text channel with a given name
        that is only visible to roles or members that are specified.
        """
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
        """This makes a voice channel with a given name
        that is only visible to roles or members that are specified.
        """
        overwrites = self.create_overwrites(ctx, *objects)
        await ctx.guild.create_voice_channel(name, overwrites=overwrites, reason="Very secret business.")

    @secret.command()
    @commands.guild_only()
    async def emoji(self, ctx, emoji: nextcord.PartialEmoji, *roles: nextcord.Role):
        """This clones a given emoji that only specified roles
        are allowed to use.
        """
        # fetch the emoji asset and read it as bytes.
        emoji_bytes = await emoji.read()
        # the key parameter here is `roles`, which controls
        # what roles are able to use the emoji.
        await ctx.guild.create_custom_emoji(
            name=emoji.name,
            image=emoji_bytes,
            roles=roles,
            reason="Very secret business.",
        )

    ## == BACKGROUND TASKS == ##
    # Background tasks are started in __init__

    # Simple background task using asyncio
    async def asyncio_counter_task(self):
        await self.bot.wait_until_ready()
        counter = 0
        channel = self.bot.get_channel(self.channel_id)
        while not self.bot.is_closed() and counter < 3:
            counter += 1
            await channel.send(f"Asyncio Counter (demonstrates `asyncio.create_task`): {counter}")
            await asyncio.sleep(5)

    # Background task using nextcord.ext.tasks
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
        await self.bot.wait_until_ready()  # wait until the bot logs in

    # NOTE: this won't actually work in our example cog
    # since we are using features that prevent cog hot loading
    def cog_unload(self) -> None:
        self.bg_counter_task.cancel()
        return super().cog_unload()

    ## == CONVERTERS == ##
    # User converter w/ error handler
    @commands.command()
    async def userinfo(self, ctx, user: nextcord.User):
        # In the command signature above, you can see that the `user`
        # parameter is typehinted to `nextcord.User`. This means that
        # during command invocation we will attempt to convert
        # the value passed as `user` to a `nextcord.User` instance.
        # The documentation notes what can be converted, in the case of `nextcord.User`
        # you pass an ID, mention or username (discrim optional)
        # E.g. 80088516616269824, @Danny or Danny#0007

        # If the conversion is successful, we will have a `nextcord.User` instance
        # and can do the following:
        user_id = user.id
        username = user.name
        avatar = user.avatar.url
        await ctx.send(f"User found: {user_id} -- {username}\n{avatar}")

    @userinfo.error
    async def userinfo_error(self, ctx, error: commands.CommandError):
        # if the conversion above fails for any reason, it will raise `commands.BadArgument`
        # so we handle this in this error handler:
        if isinstance(error, commands.BadArgument):
            return await ctx.send("Couldn't find that user.")

    # Custom converter example
    @commands.command()
    async def notify(self, ctx, target: ChannelOrMemberConverter):
        # This command signature utilises the custom converter class written above
        # What will happen during command invocation is that the `target` above will be passed to
        # the `argument` parameter of the `ChannelOrMemberConverter.convert` method and
        # the conversion will go through the process defined there.
        await target.send(f"Hello, {target.name}!")

    # Union converter example
    @commands.command()
    async def ignore(self, ctx, target: Union[nextcord.Member, nextcord.TextChannel]):
        # The `commands` framework attempts a conversion of each type in this Union *in order*.
        # So, it will attempt to convert whatever is passed to `target` to a `nextcord.Member` instance.
        # If that fails, it will attempt to convert it to a `nextcord.TextChannel` instance.
        # See: https://nextcord.readthedocs.io/en/latest/ext/commands/commands.html#typing-union
        # NOTE: If a Union typehint converter fails it will raise `commands.BadUnionArgument`
        # instead of `commands.BadArgument`.

        # To check the resulting type, `isinstance` is used
        if isinstance(target, nextcord.Member):
            await ctx.send(f"Member found: {target.mention}, adding them to the ignore list.")
        elif isinstance(target, nextcord.TextChannel):  # this could be an `else` but for completeness' sake.
            await ctx.send(f"Channel found: {target.mention}, adding it to the ignore list.")

    # Built-in type converters
    @commands.command()
    async def multiply(self, ctx, number: int, maybe: bool):
        # `bool` is a slightly special case, as shown here:
        # See: https://nextcord.readthedocs.io/en/latest/ext/commands/commands.html#bool
        if maybe is True:
            return await ctx.send(number * 2)
        await ctx.send(number * 5)

    ### === CUSTOM CONTEXT === ###
    # Custom context example
    @commands.command()
    async def guess(self, ctx, number: int):
        """Guess a random number from 1 to 6."""
        value = random.randint(1, 6)
        # with your new helper function, you can add a
        # green check mark if the guess was correct,
        # or a red cross mark if it wasn't
        await ctx.cc_tick(ctx, number == value)

    ### === APPLICATION COMMANDS === ###
    # Basic slash command example in a cog
    @nextcord.slash_command(description="Test command")
    async def my_slash_command(self, interaction: Interaction):
        await interaction.response.send_message("This is a slash command in a cog!")

    # Echo message
    @nextcord.slash_command(description="Repeats your message")
    async def echo(self, interaction: Interaction, arg: str = SlashOption(description="Message")):
        await interaction.response.send_message(arg)

    # Basic context menu examples
    @nextcord.user_command()
    async def my_user_command(self, interaction: Interaction, member: Member):
        await interaction.response.send_message(f"Hello, {member}!")

    @nextcord.message_command()
    async def my_message_command(self, interaction: Interaction, message: Message):
        await interaction.response.send_message(f"{message}")

    # Example slash commands with choices
    @nextcord.slash_command(description="Number choices example")
    async def choose_a_number(
        self,
        interaction: Interaction,
        number: int = SlashOption(
            name="picker",
            description="The number you want",
            choices={"one": 1, "two": 2, "three": 3},
        ),
    ):
        await interaction.response.send_message(f"You chose {number}!")

    @nextcord.slash_command(description="Member choices example")
    async def hi(
        self,
        interaction: Interaction,
        member: Member = SlashOption(name="user", description="User to say hi to"),
    ):
        await interaction.response.send_message(f"{interaction.user} just said hi to {member.mention}")

    # Subcommands example
    @nextcord.slash_command(description="Subcommand demo")
    async def main(self, interaction: Interaction):
        pass

    @main.subcommand(description="Subcommand 1")
    async def sub1(self, interaction: Interaction):
        await interaction.response.send_message("This is subcommand 1!")

    @main.subcommand(description="Subcommand 2")
    async def sub2(self, interaction: Interaction):
        await interaction.response.send_message("This is subcommand 2!")

    @main.subcommand(description="main_group subcommand group")
    async def main_group(self, interaction: Interaction):
        pass

    @main_group.subcommand(description="Subcommand group subcommand 1")
    async def subsub1(self, interaction: Interaction):
        await interaction.response.send_message("This is a subcommand group's subcommand!")

    @main_group.subcommand(description="Subcommand group subcommand 2")
    async def subsub2(self, interaction: Interaction):
        await interaction.response.send_message("This is subcommand group subcommand 2!")

    # Example autocompleted slash command
    list_of_dog_breeds = [
        "German Shepard",
        "Poodle",
        "Pug",
        "Shiba Inu",
    ]

    @nextcord.slash_command(description="Autocomplete demo")
    async def your_favorite_dog(
        self,
        interaction: Interaction,
        dog: str = SlashOption(
            name="dog",
            description="Choose the best dog from this autocompleted list!",
        ),
    ):
        # sends the autocompleted result
        await interaction.response.send_message(f"Your favorite dog is {dog}!")

    @your_favorite_dog.on_autocomplete("dog")
    async def favorite_dog(self, interaction: Interaction, dog: str):
        if not dog:
            # send the full autocomplete list
            await interaction.response.send_autocomplete(self.list_of_dog_breeds)
            return
        # send a list of nearest matches from the list of dog breeds
        get_near_dog = [breed for breed in self.list_of_dog_breeds if breed.lower().startswith(dog.lower())]
        await interaction.response.send_autocomplete(get_near_dog)

    ### === MODALS === ###
    # Example basic modal slash command
    @nextcord.slash_command(name="pet", description="Describe your favorite pet")
    async def send(self, interaction: Interaction):
        modal = Pet()
        await interaction.response.send_modal(modal)

    # Example persistent modal slash command
    @nextcord.slash_command(name="feedback", description="Send your feedback to the bot developer!")
    async def feedback(self, interaction: Interaction):
        await interaction.response.send_modal(CogPersists.FeedbackModal())

    ### === VIEWS === ###
    # Demo view with a simple search button
    @commands.command(name="lmgtfy")
    async def lmgtfy(self, ctx, *, query: str):
        """Returns a google link for a query"""
        await ctx.send(f"Google Result for: `{query}`", view=Google(query))

    # Demo view with a confirmation menu
    @commands.command(name="ask")
    async def ask(self, ctx):
        """Asks the user a question to confirm something."""
        # We create the view and assign it to a variable so we can wait for it later.
        view = Confirm()
        await ctx.send("Do you want to continue?", view=view)
        # Wait for the View to stop listening for input...
        await view.wait()
        if view.value is None:
            print("Timed out...")
        elif view.value:
            print("Confirmed...")
        else:
            print("Cancelled...")

    # Demo view with a counter button
    @commands.command(name="counter")
    async def counter(self, ctx):
        """Starts a counter for pressing."""
        await ctx.send("Press!", view=Counter())

    # Demo view with an ephemeral counter button
    @commands.command(name="my_counter")
    async def my_counter(self, ctx):
        """Starts an ephemeral counter for pressing."""
        await ctx.send("Press!", view=EphemeralCounter())

    # Demo view with a dropdown select
    @commands.command(name="color")
    async def color(self, ctx):
        """Sends a message with our dropdown containing colors"""
        view = DropdownView()
        await ctx.send("Pick your favourite colour:", view=view)

    # Demo view with persistence
    @commands.command()
    @commands.is_owner()
    async def prepare(self, ctx):
        """Starts a persistent view."""
        # In order for a persistent view to be listened to, it needs to be sent to an actual message.
        # Call this method once just to store it somewhere.
        # In a more complicated program you might fetch the message_id from a database for use later.
        # However this is outside of the scope of this simple example.
        await ctx.send("What's your favourite colour?", view=CogPersists.PersistentView())

    # Demo TicTacToe game view
    @commands.command()
    async def tic(self, ctx):
        """Starts a tic-tac-toe game with yourself."""
        await ctx.send("Tic Tac Toe: X goes first", view=TicTacToe())

    # Database Test Command
    @commands.command()
    async def db_test(self, ctx):
        """Tests the database connection and SQLModel."""
        from sqlmodel import select

        from app.common.alchemy import get_session
        from app.db.models import GuildExtensionSettings

        await ctx.send("Starting Database Test...")

        try:
            # We use the generator manually here since nextcord doesn't support
            # FastAPI-style dependency injection out of the box for commands
            session_gen = get_session()
            session = next(session_gen)

            try:
                # 1. Create
                test_setting = GuildExtensionSettings(
                    guild_id=ctx.guild.id,
                    extension_name="test_extension",
                    gadget_type="test_gadget",
                    is_enabled=True,
                )
                session.merge(test_setting)  # merge to handle potential existing PK
                session.commit()
                await ctx.send("✅ Inserted/Merged test record.")

                # 2. Read
                statement = select(GuildExtensionSettings).where(
                    GuildExtensionSettings.guild_id == ctx.guild.id,
                    GuildExtensionSettings.extension_name == "test_extension",
                )
                result = session.exec(statement).first()
                if result:
                    await ctx.send(f"✅ Read record: {result}")
                else:
                    await ctx.send("❌ Failed to read record.")

                # 3. Clean up (Delete)
                if result:
                    session.delete(result)
                    session.commit()
                    await ctx.send("✅ Deleted test record.")

            finally:
                session.close()

        except Exception as e:
            await ctx.send(f"❌ Error: {e}")


### === TODO LIST COG === ###
class TodoCog(GuildAwareCog):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        # We use a separate engine/session strategy for the example.
        # In a real app, you might inject the session or use a global one differently.
        self.engine = init_connection_engine()

    @commands.group(invoke_without_command=True)
    async def todo(self, ctx):
        """Manage your todo list."""
        await ctx.send_help(ctx.command)

    @todo.command(name="list")
    async def todo_list(self, ctx):
        """List your todos."""
        with Session(self.engine) as session:
            statement = select(TodoItem).where(TodoItem.user_id == str(ctx.author.id))
            results = session.exec(statement).all()

            if not results:
                await ctx.send("You have no todos!")
                return

            msg = "**Your Todos:**\n"
            for todo in results:
                status = "✅" if todo.is_completed else "❌"
                msg += f"{todo.id}. [{status}] {todo.content}\n"
            await ctx.send(msg)

    @todo.command(name="add")
    async def todo_add(self, ctx, *, content: str):
        """Add a new todo."""
        with Session(self.engine) as session:
            todo = TodoItem(content=content, user_id=str(ctx.author.id))
            session.add(todo)
            session.commit()
            session.refresh(todo)
            await ctx.send(f"Added todo: {todo.content} (ID: {todo.id})")

    @todo.command(name="complete")
    async def todo_complete(self, ctx, todo_id: int):
        """Mark a todo as complete."""
        with Session(self.engine) as session:
            # We must be careful to only let users complete their own todos
            todo = session.get(TodoItem, todo_id)
            if not todo:
                await ctx.send("Todo not found.")
                return

            if todo.user_id != str(ctx.author.id):
                await ctx.send("You can only complete your own todos.")
                return

            todo.is_completed = True
            session.add(todo)
            session.commit()
            await ctx.send(f"Todo {todo.id} marked as complete!")

    @todo.command(name="delete")
    async def todo_delete(self, ctx, todo_id: int):
        """Delete a todo."""
        with Session(self.engine) as session:
            todo = session.get(TodoItem, todo_id)
            if not todo:
                await ctx.send("Todo not found.")
                return

            if todo.user_id != str(ctx.author.id):
                await ctx.send("You can only delete your own todos.")
                return

            session.delete(todo)
            session.commit()
            await ctx.send(f"Todo {todo_id} deleted!")


def setup(bot: commands.Bot):
    bot.add_cog(ExamplesCog(bot))
    bot.add_cog(TodoCog(bot))
