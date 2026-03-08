from fasthtml.common import *
from sqlmodel import Session, desc, select

from app.ui.components import Card

from .blueprint import TodoItem, engine


def welcome_widget():
    """A simple welcome widget."""
    return Card(
        "Welcome to Powercord!",
        Div(
            P("This is an example widget from the 'example' extension."),
            P("Widgets are FastHTML components that can be arranged on a public-facing page."),
        ),
    )


def another_widget():
    """Another example widget."""
    return Card(
        "Another Example",
        Div(
            P("You can have multiple widgets per extension."),
            P("This demonstrates how multiple components can be discovered and rendered."),
        ),
    )


def todo_widget():
    """A widget acting as a public Todo List display.

    This demonstrates fetching data from the database using a manually managed
    session, and rendering it dynamically into a list of HTML LI elements.
    """

    items = []
    try:
        # We manually create a session since widgets are simple functions
        # and do not have access to FastAPI's dependency injection
        with Session(engine) as session:
            # show last 10 items
            statement = select(TodoItem).order_by(desc(TodoItem.id)).limit(10)
            todos = session.exec(statement).all()

        if not todos:
            items.append(Li("No todos yet! Add some via Discord or API."))
        else:
            for todo in todos:
                status = "✅" if todo.is_completed else "❌"
                items.append(Li(f"{status} {todo.content} (User ID: {todo.user_id})"))

    except Exception as e:
        items.append(Li(f"Error loading todos: {str(e)}", style="color: red;"))

    return Card(
        "Recent Todos",
        Div(
            Ul(*items),
            Div("Manage via Discord or API", cls="mt-4 opacity-70 text-sm"),
        ),
    )


def admin_example_controls_widget():
    """Admin widget to control the example bot counters.

    This widget starts with the prefix 'admin_' to prevent it from showing up
    in public layouts. It uses FastHTML forms to send POST requests to the dashboard.
    """
    return Card(
        "Example Controls",
        Div(
            P("Use these buttons to toggle the example counters in Discord.", cls="mb-4 opacity-80"),
            Div(
                Form(
                    Button("Start Counters", cls="btn btn-primary"),
                    action="/admin/examples/counters/start",
                    method="post",
                ),
                Form(
                    Button("Stop Counters", cls="btn btn-secondary"),
                    action="/admin/examples/counters/stop",
                    method="post",
                ),
                cls="flex flex-wrap gap-4",
            ),
        ),
    )
