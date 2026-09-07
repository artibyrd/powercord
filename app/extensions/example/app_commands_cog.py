"""Example application commands: slash commands, user commands, message commands."""

import nextcord
from nextcord import Interaction, Member, Message, SlashOption
from nextcord.ext import commands

from app.common.guild_cog import GuildAwareCog

from .modals import Pet


class AppCommandsCog(GuildAwareCog):
    """Cog showcasing Nextcord application commands, context menus, and modals."""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

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
        await interaction.response.send_message(f"Your favorite dog is {dog}!")

    @your_favorite_dog.on_autocomplete("dog")
    async def favorite_dog(self, interaction: Interaction, dog: str):
        if not dog:
            await interaction.response.send_autocomplete(self.list_of_dog_breeds)
            return
        get_near_dog = [breed for breed in self.list_of_dog_breeds if breed.lower().startswith(dog.lower())]
        await interaction.response.send_autocomplete(get_near_dog)

    # Example basic modal slash command
    @nextcord.slash_command(name="pet", description="Describe your favorite pet")
    async def send(self, interaction: Interaction):
        modal = Pet()
        await interaction.response.send_modal(modal)

    # Example persistent modal slash command
    @nextcord.slash_command(name="feedback", description="Send your feedback to the bot developer!")
    async def feedback(self, interaction: Interaction):
        from .cog import CogPersists

        await interaction.response.send_modal(CogPersists.FeedbackModal())
