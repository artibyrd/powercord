from typing import Optional

from sqlmodel import Field, SQLModel

from app.common.alchemy import init_connection_engine


class TodoItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str
    is_completed: bool = Field(default=False)
    user_id: str  # Discord User ID


try:
    engine = init_connection_engine()
except Exception as e:
    print(f"Warning: Could not initialize engine for example extension: {e}")
