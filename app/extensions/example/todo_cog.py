"""Example Todo list cog showcasing SQLModel database operations."""

from nextcord.ext import commands
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.common.guild_cog import GuildAwareCog

from .blueprint import TodoItem


class TodoCog(GuildAwareCog):
    """Cog for managing user todo items backed by SQLModel."""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
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
