from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.common.alchemy import get_session

from .blueprint import TodoItem

router = APIRouter()


@router.get("/")
async def read_example():
    """Root endpoint for the example sprocket."""
    return {"message": "Hello from the example sprocket!"}


@router.get("/todos/")
async def read_todos(session: Session = Depends(get_session)):
    """List all todo items."""
    todos = session.exec(select(TodoItem)).all()
    return todos


@router.post("/todos/")
async def create_todo(todo: TodoItem, session: Session = Depends(get_session)):
    """Create a new todo item.

    Demonstrates how to handle POST requests and insert data into the database
    via SQLAlchemy/SQLModel sessions managed by FastAPI dependencies.
    """
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo


@router.put("/todos/{todo_id}")
async def update_todo(todo_id: int, todo: TodoItem, session: Session = Depends(get_session)):
    """Update a todo item (e.g. mark as complete)."""
    db_todo = session.get(TodoItem, todo_id)
    if not db_todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    # Update fields
    db_todo.content = todo.content
    db_todo.is_completed = todo.is_completed
    db_todo.user_id = todo.user_id

    session.add(db_todo)
    session.commit()
    session.refresh(db_todo)
    return db_todo


@router.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int, session: Session = Depends(get_session)):
    """Delete a todo item.

    Demonstrates handling a DELETE request by fetching the existing model
    instance before deleting it from the session.
    """
    db_todo = session.get(TodoItem, todo_id)
    if not db_todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    session.delete(db_todo)
    session.commit()
    return {"ok": True}
