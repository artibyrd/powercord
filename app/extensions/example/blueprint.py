from typing import Optional

from sqlmodel import Field, SQLModel

from app.common.alchemy import init_connection_engine


class TodoItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str
    is_completed: bool = Field(default=False)
    user_id: str  # Discord User ID


# Create the table if it doesn't exist
# Note: In a production app, use Alembic migrations.
# This is a shortcut for the example extension to ensure it works out of the box.
try:
    engine = init_connection_engine()
    SQLModel.metadata.create_all(engine)
except Exception as e:
    print(f"Warning: Could not create tables for example extension: {e}")
