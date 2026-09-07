"""Example cog demonstrating UI views and interactive button/dropdown components."""

from nextcord.ext import commands

from app.common.guild_cog import GuildAwareCog

from .views import Confirm, Counter, DropdownView, EphemeralCounter, Google, TicTacToe


class ViewsCog(GuildAwareCog):
    """Cog demonstrating UI view interactions and database checks."""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    # Demo view with a simple search button
    @commands.command(name="lmgtfy")
    async def lmgtfy(self, ctx, *, query: str):
        """Returns a google link for a query."""
        await ctx.send(f"Google Result for: `{query}`", view=Google(query))

    # Demo view with a confirmation menu
    @commands.command(name="ask")
    async def ask(self, ctx):
        """Asks the user a question to confirm something."""
        view = Confirm()
        await ctx.send("Do you want to continue?", view=view)
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
        """Sends a message with our dropdown containing colors."""
        view = DropdownView()
        await ctx.send("Pick your favourite colour:", view=view)

    # Demo view with persistence
    @commands.command()
    @commands.is_owner()
    async def prepare(self, ctx):
        """Starts a persistent view."""
        from .cog import CogPersists

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
                session.merge(test_setting)
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
