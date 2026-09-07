# mypy: ignore-errors
from __future__ import annotations

from fasthtml.common import *

from app.common.extension_hooks import supports_delete_data
from app.common.extension_loader import GadgetInspector
from app.ui.components import Card
from app.ui.helpers import (
    SCOPE_ADMIN_DASHBOARD,
    SCOPE_PUBLIC,
    get_widget_name,
    get_widget_settings,
    is_gadget_enabled,
)


def format_extension_title(extension_name: str) -> str:
    """Format an extension identifier into a clean, human-readable title."""
    if extension_name.lower() in ("midi_library", "midilibrary"):
        return "MIDI Library"
    return extension_name.replace("_", " ").title()


def _humanize_widget_name(ext_name: str, raw_name: str) -> str:
    """Convert an internal widget function name to a human-readable label."""
    inspector = GadgetInspector()
    all_widgets = inspector.inspect_widgets()
    for func in all_widgets.get(ext_name, []):
        if getattr(func, "__name__", None) == raw_name:
            display = getattr(func, "display_name", None)
            if display:
                return display

    name = raw_name
    name = name.removeprefix("widget_")
    name = name.replace("_", " ").strip()
    return name.title() if name else raw_name


def _get_ordered_widgets(scope_id: int) -> list[dict]:
    """Build a sorted list of all widgets with their current settings."""
    inspector = GadgetInspector()
    all_widgets_by_ext = inspector.inspect_widgets()
    settings = get_widget_settings(scope_id)

    widgets = []
    for ext_name, widget_funcs in all_widgets_by_ext.items():
        if not is_gadget_enabled(0, ext_name, "widget"):
            continue

        for func in widget_funcs:
            wname = get_widget_name(func)
            if not wname:
                continue

            # Filter based on scope
            is_admin_widget = wname.startswith("admin_")
            is_guild_admin_widget = wname.startswith("guild_admin_")

            if scope_id == SCOPE_PUBLIC and (is_admin_widget or is_guild_admin_widget):
                continue

            if scope_id == SCOPE_ADMIN_DASHBOARD and not is_admin_widget:
                continue

            if scope_id > 1 and not is_guild_admin_widget:
                continue

            ws = settings.get(wname, {})
            pos_cfg = ws.get("position_config")

            default_pos = getattr(func, "default_pos", None) or getattr(func, "position_config", None)

            if default_pos in ("left", "right"):
                if pos_cfg != "right":
                    pos_cfg = "left"
            elif default_pos in ("bottom-right", "bottom-left", "top-right", "top-left"):
                if pos_cfg not in ("bottom-right", "bottom-left", "top-right", "top-left"):
                    pos_cfg = "bottom-right"

            widgets.append(
                {
                    "ext": ext_name,
                    "widget": wname,
                    "enabled": ws.get("is_enabled", False),
                    "span": ws.get("column_span", 4),
                    "order": ws.get("display_order", 99),
                    "position_config": pos_cfg,
                    "default_pos": default_pos,
                }
            )

    widgets.sort(
        key=lambda w: (
            not w["enabled"],
            w["enabled"]
            and w.get("default_pos") in ("left", "right", "bottom-right", "bottom-left", "top-right", "top-left"),
            w["order"],
        )
    )
    return widgets


def server_extension_card(
    guild_id: int,
    extension_name: str,
    gadgets: list[str],
    enabled_cogs: list[str],
    enabled_sprockets: list[str],
    enabled_widgets: list[str],
    disabled: bool = False,
) -> FT:
    """Renders a card for a single extension with toggles for its components, for a specific server."""
    display_title = format_extension_title(extension_name)

    details_link = A(
        display_title,
        cls="flex-grow font-bold text-lg cursor-pointer hover:underline text-base-content",
        hx_get=f"/dashboard/{guild_id}/extensions/{extension_name}/details",
        hx_target="#modal-container",
        hx_swap="innerHTML",
        style="text-decoration-color: currentColor;",
    )

    is_enabled = (
        (extension_name in enabled_cogs) or (extension_name in enabled_sprockets) or (extension_name in enabled_widgets)
    )

    if disabled:
        toggle_form = Form(
            Label(
                Input(
                    type="checkbox",
                    name="enabled",
                    value="on",
                    checked="checked" if is_enabled else False,
                    disabled=True,
                    id=f"all-{extension_name}-server-{guild_id}",
                    cls="toggle toggle-primary toggle-sm cursor-not-allowed opacity-50",
                ),
                cls="label cursor-pointer p-0",
            ),
            Hidden(name="extension_name", value=extension_name),
            Hidden(name="gadget_type", value="all"),
            cls="flex items-center",
            id=f"form-all-{extension_name}-server-{guild_id}",
        )
    else:
        toggle_form = Form(
            Label(
                Input(
                    type="checkbox",
                    name="enabled",
                    value="on",
                    checked="checked" if is_enabled else False,
                    id=f"all-{extension_name}-server-{guild_id}",
                    cls="toggle toggle-primary toggle-sm",
                    hx_post=f"/dashboard/{guild_id}/extensions/toggle",
                    hx_trigger="change",
                    hx_target=f"#server-extension-{extension_name}-{guild_id}",
                    hx_swap="outerHTML",
                    hx_include="closest form",
                ),
                cls="label cursor-pointer p-0",
            ),
            Hidden(name="extension_name", value=extension_name),
            Hidden(name="gadget_type", value="all"),
            cls="flex items-center",
            id=f"form-all-{extension_name}-server-{guild_id}",
        )

    delete_btn = None
    if supports_delete_data(extension_name) and not disabled:
        delete_btn = Button(
            I(cls="fa-solid fa-trash-can mr-1"),
            "Delete Data",
            cls="btn btn-error btn-xs",
            hx_get=f"/dashboard/{guild_id}/extensions/{extension_name}/confirm-delete",
            hx_target="#modal-container",
            hx_swap="innerHTML",
        )

    title_comp = Div(details_link, toggle_form, cls="flex items-center w-full justify-between")
    bottom_action = Div(delete_btn, cls="flex justify-end mt-4") if delete_btn else Div(cls="mt-4 min-h-[24px]")

    return Card(
        title_comp,
        bottom_action,
        id=f"server-extension-{extension_name}-{guild_id}",
        cls="min-h-[110px] flex flex-col justify-between",
    )
