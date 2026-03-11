import logging
import sys

from fasthtml.common import FT, H2, Button, Div, NotStr, P
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.db.models import CustomContentItem


def admin_custom_content_editor(access_token: str | None = None) -> FT:
    """Admin editor panel for creating custom HTML/Markdown widgets."""
    return Div(
        H2("Custom Content Configuration", cls="text-xl font-bold mb-4"),
        P("Manage custom content widgets that can be placed on the public layout.", cls="mb-4 opacity-80"),
        Div(
            Button(
                "Create New Widget",
                hx_get="/admin/custom_content/new",
                hx_target="#cc-editor-area",
                cls="btn btn-primary mb-4",
            ),
            Div(
                # Container for list
                Div(id="cc-list", hx_get="/admin/custom_content", hx_trigger="load"),
                cls="mb-8",
            ),
            # Container for form
            Div(id="cc-editor-area"),
            cls="grid grid-cols-1 gap-4",
        ),
        cls="card bg-base-100 shadow-xl p-6 mb-8 border border-base-content/10",
    )


def _inject_dynamic_widget(
    item_id: int, item_name: str, item_content: str, item_format: str, item_has_frame: bool = True
):
    """Dynamically register a widget function to this module's namespace."""

    def custom_widget_func(**kwargs) -> FT:
        # Fetch the latest content on render to ensure it's up to date
        engine = init_connection_engine()
        with Session(engine) as session:
            item = session.get(CustomContentItem, item_id)
            if not item:
                return P("Custom Content not found.", cls="text-error")

            # Core content node
            if item.format == "html":
                content_node = Div(NotStr(item.content), cls=f"custom-html-{item_id}")
            else:
                # Fix #3: Render markdown server-side so nh3 can sanitize the
                # resulting HTML. This prevents javascript: URL injection that
                # would bypass server-side sanitization in a client-side renderer.
                import markdown as md

                from app.db.models import _sanitize_content

                rendered_html = md.markdown(
                    item.content,
                    extensions=["extra", "codehilite", "sane_lists"],
                )
                safe_html = _sanitize_content(rendered_html)
                content_node = Div(
                    NotStr(safe_html),
                    cls=f"prose prose-invert custom-md-{item_id}",
                )

            # Apply UI framing
            if item.has_frame:
                return Div(
                    H2(item.name, cls="text-xl font-bold mb-4 opacity-80"),
                    content_node,
                    cls="custom-widget card bg-base-100 shadow-xl p-6 mb-8 border border-base-content/10",
                )
            else:
                return Div(content_node, cls="custom-widget")

    # Needs to start with widget_ to be public. Name maps to DB layout config
    safe_name = "".join(c for c in item_name if c.isalnum() or c == "_")
    func_name = f"widget_cc_{item_id}_{safe_name}"
    custom_widget_func.__name__ = func_name
    custom_widget_func.display_name = item_name  # type: ignore[attr-defined]  # Dynamic attr for layout editor

    current_module = sys.modules[__name__]
    setattr(current_module, func_name, custom_widget_func)
    logging.info(f"Registered dynamic widget: {func_name}")


def _load_existing_widgets():
    """Load existing widgets from DB on module initialization."""
    try:
        engine = init_connection_engine()
        with Session(engine) as session:
            items = session.exec(select(CustomContentItem)).all()
            for item in items:
                _inject_dynamic_widget(item.id, item.name, item.content, item.format, item.has_frame)
    except Exception as e:
        logging.error(f"Failed to load custom widgets. DB might not be initialized yet. {e}")


_load_existing_widgets()
