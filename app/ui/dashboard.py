# mypy: ignore-errors
from __future__ import annotations

import logging
import sys
from pathlib import Path

from fasthtml.common import *
from fasthtml.core import APIRouter

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


from app.common.extension_hooks import run_hook, supports_delete_data
from app.common.extension_loader import GadgetInspector
from app.common.extension_manager import get_installed_extensions
from app.ui.components import Card
from app.ui.helpers import (
    SCOPE_ADMIN_DASHBOARD,
    SCOPE_PUBLIC,
    get_admin_guilds,
    get_guild_cogs,
    get_guild_sprockets,
    get_guild_widgets,
    get_internal_api_client,
    get_widget_name,
    get_widget_settings,
    is_gadget_enabled,
    notify_api_of_config_change,
    update_guild_extension_setting,
    update_widget_setting,
)
from app.ui.page import DashboardPage


def server_extension_card(
    guild_id: int,
    extension_name: str,
    gadgets: list[str],
    enabled_cogs: list[str],
    enabled_sprockets: list[str],
    enabled_widgets: list[str],
) -> FT:
    """Renders a card for a single extension with toggles for its components, for a specific server."""

    details_link = A(
        extension_name.capitalize(),
        cls="flex-grow font-bold text-lg cursor-pointer hover:underline text-base-content",
        hx_get=f"/dashboard/{guild_id}/extensions/{extension_name}/details",
        hx_target="#modal-container",
        hx_swap="innerHTML",
        style="text-decoration-color: currentColor;",
    )

    is_enabled = (
        (extension_name in enabled_cogs) or (extension_name in enabled_sprockets) or (extension_name in enabled_widgets)
    )

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

    # "Delete Data" button — only shown for extensions that registered a cleanup hook
    delete_btn = None
    if supports_delete_data(extension_name):
        delete_btn = Button(
            I(cls="fa-solid fa-trash-can mr-1"),
            "Delete Data",
            cls="btn btn-error btn-xs mt-2",
            hx_get=f"/dashboard/{guild_id}/extensions/{extension_name}/confirm-delete",
            hx_target="#modal-container",
            hx_swap="innerHTML",
        )

    title_comp = Div(details_link, toggle_form, cls="flex items-center w-full justify-between")

    return Card(
        title_comp,
        Div(delete_btn, cls="flex justify-end") if delete_btn else "",
        id=f"server-extension-{extension_name}-{guild_id}",
    )


# ... (Previous code remains, jumping to widget section)

dashboard_router = APIRouter()


@dashboard_router("/dashboard/{guild_id:int}/extensions/{extension_name}/details", methods=["GET"])
async def server_extension_details_route(guild_id: int, extension_name: str, req):
    """Returns a modal with the extension details for a specific server dashboard."""
    from app.ui.helpers import get_extension_details_modal

    auth_data = req.session.get("auth", {})
    token_data = auth_data.get("token_data", {})
    access_token = token_data.get("access_token")
    return get_extension_details_modal(extension_name, access_token=access_token)


@dashboard_router("/dashboard/{guild_id:int}/extensions/{extension_name}/confirm-delete", methods=["GET"])
async def confirm_delete_data_route(guild_id: int, extension_name: str, req):
    """Returns a confirmation modal before deleting extension data for a guild."""
    modal_content = Dialog(
        Div(
            H3(
                I(cls="fa-solid fa-triangle-exclamation mr-2 text-warning"),
                "Delete Server Data",
                cls="font-bold text-lg",
            ),
            P(
                "This will permanently delete all ",
                Strong(extension_name.capitalize()),
                " data for this server. This action cannot be undone.",
                cls="py-4",
            ),
            Div(
                Form(
                    method="dialog",
                    children=[
                        Button("Cancel", cls="btn btn-ghost"),
                    ],
                ),
                Button(
                    I(cls="fa-solid fa-trash-can mr-1"),
                    "Confirm Delete",
                    cls="btn btn-error",
                    hx_post=f"/dashboard/{guild_id}/extensions/{extension_name}/delete-data",
                    hx_target=f"#server-extension-{extension_name}-{guild_id}",
                    hx_swap="outerHTML",
                ),
                cls="modal-action",
            ),
            cls="modal-box",
        ),
        # Clicking backdrop closes modal
        Form(method="dialog", cls="modal-backdrop", children=[Button("close")]),
        id="modal-container",
        cls="modal modal-open",
    )
    return modal_content


@dashboard_router("/dashboard/{guild_id:int}/extensions/{extension_name}/delete-data", methods=["POST"])
async def delete_server_data_route(guild_id: int, extension_name: str, req):
    """Executes deletion of all extension-specific data for a guild."""
    if not supports_delete_data(extension_name):
        return P(f"Extension '{extension_name}' does not support data deletion.", cls="text-error")

    run_hook(extension_name, "delete_guild_data", guild_id=guild_id)
    logging.info(f"Deleted server data for extension '{extension_name}' on guild {guild_id}.")

    # Re-render the extension card to reflect the updated state
    inspector = GadgetInspector()
    all_extensions = inspector.inspect_extensions()
    gadgets = all_extensions.get(extension_name, [])
    enabled_cogs = get_guild_cogs(guild_id)
    enabled_sprockets = get_guild_sprockets(guild_id)
    enabled_widgets = get_guild_widgets(guild_id)

    card = server_extension_card(guild_id, extension_name, gadgets, enabled_cogs, enabled_sprockets, enabled_widgets)
    # Close the modal via out-of-band swap and add a success toast
    close_modal = Dialog(id="modal-container", hx_swap_oob="true")
    toast = Div(
        Div(
            Span(f"✅ {extension_name.capitalize()} data deleted for this server."),
            cls="alert alert-success",
        ),
        id="toast-container",
        hx_swap_oob="true",
        cls="toast toast-end",
        # Auto-remove toast after 4 seconds
        **{"_": "on load wait 4s then remove me"},
    )
    return card, close_modal, toast


@dashboard_router("/dashboard/{guild_id:int}/extensions/toggle", methods=["POST"])
async def toggle_server_gadget_route(guild_id: int, req):
    """Handles toggling an extension on/off for a specific server."""
    form_data = await req.form()
    extension_name = form_data.get("extension_name")
    is_enabled = form_data.get("enabled") == "on"

    logging.info(f"Toggle server {guild_id}: Ext={extension_name} Enabled={is_enabled}")

    inspector = GadgetInspector()
    all_extensions = inspector.inspect_extensions()
    gadgets = all_extensions.get(extension_name, [])

    for g_type in gadgets:
        update_guild_extension_setting(guild_id, extension_name, g_type, is_enabled)

    if "sprocket" in gadgets:
        await notify_api_of_config_change(guild_id)

    enabled_cogs = get_guild_cogs(guild_id)
    enabled_sprockets = get_guild_sprockets(guild_id)
    enabled_widgets = get_guild_widgets(guild_id)

    return server_extension_card(guild_id, extension_name, gadgets, enabled_cogs, enabled_sprockets, enabled_widgets)


@dashboard_router("/dashboard/{guild_id:int}")
async def dashboard(guild_id: int, sess):
    """Displays a dashboard for a specific server."""
    auth = sess.get("auth", {})
    user_access_token = auth.get("token_data", {}).get("access_token")
    if not user_access_token:
        return Titled("Error", P("Could not retrieve necessary tokens."))

    try:
        user_id = int(auth.get("id"))
        admin_guilds = await get_admin_guilds(user_access_token, user_id)
        guild = admin_guilds.get(str(guild_id), {"name": "Unknown Server"})
    except Exception as e:
        return Titled("Error", P(f"Failed to fetch guild information: {e}"))

    inspector = GadgetInspector()
    all_extensions = inspector.inspect_extensions()

    if "powerloader" in all_extensions:
        del all_extensions["powerloader"]

    # Filter out global_only extensions from being configurable per-server
    global_only_extensions = {ext["name"] for ext in get_installed_extensions() if ext.get("global_only")}

    enabled_cogs = get_guild_cogs(guild_id)
    enabled_sprockets = get_guild_sprockets(guild_id)
    enabled_widgets = get_guild_widgets(guild_id)

    global_cogs = get_guild_cogs(0)
    global_sprockets = get_guild_sprockets(0)
    global_widgets = get_guild_widgets(0)

    server_extension_cards = []
    for name, gadgets in all_extensions.items():
        if name in global_only_extensions:
            continue

        server_gadgets = []
        if "cog" in gadgets and name in global_cogs:
            server_gadgets.append("cog")
        if "sprocket" in gadgets and name in global_sprockets:
            server_gadgets.append("sprocket")
        if "widget" in gadgets and name in global_widgets:
            server_gadgets.append("widget")

        if server_gadgets:
            server_extension_cards.append(
                server_extension_card(guild_id, name, server_gadgets, enabled_cogs, enabled_sprockets, enabled_widgets)
            )

    server_extensions = Div(
        H2("Manage Extensions (Server)", cls="text-2xl font-bold mb-4"),
        P(
            "Toggle extension components for this server. Only globally enabled components are shown here.",
            cls="mb-4 opacity-80",
        ),
        Div(*server_extension_cards, cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8")
        if server_extension_cards
        else P("No extensions are currently globally enabled.", cls="opacity-60 italic"),
        cls="mb-8 mt-8",
    )

    # Fetch widgets for this guild
    all_widgets = inspector.inspect_widgets()
    settings = get_widget_settings(guild_id)
    if not settings:
        for ext_name in global_widgets:
            update_guild_extension_setting(guild_id, ext_name, "widget", True)
        settings = get_widget_settings(guild_id)

    fixed_widgets = []
    floating_widgets = []
    grid_widgets = []

    for ext_name, widget_funcs in all_widgets.items():
        if not is_gadget_enabled(guild_id, ext_name, "widget"):
            continue

        for func in widget_funcs:
            w_name = get_widget_name(func)
            if not w_name or not w_name.startswith("guild_admin_"):
                continue

            widget_setting = settings.get(w_name, {})
            if widget_setting.get("is_enabled", False):
                try:
                    import inspect

                    sig = inspect.signature(func)
                    kwargs = {}
                    if "guild_id" in sig.parameters:
                        kwargs["guild_id"] = guild_id
                    if "access_token" in sig.parameters:
                        kwargs["access_token"] = user_access_token

                    pos_cfg = widget_setting.get("position_config") or getattr(func, "position_config", None)
                    widget_data = {
                        "component": func(**kwargs),
                        "order": widget_setting.get("display_order", 99),
                        "span": widget_setting.get("column_span", 4),
                        "position_config": pos_cfg,
                    }

                    if pos_cfg in ("left", "right"):
                        fixed_widgets.append(widget_data)
                    elif pos_cfg in ("bottom-right", "bottom-left", "top-right", "top-left"):
                        floating_widgets.append(widget_data)
                    else:
                        grid_widgets.append(widget_data)
                except Exception as e:
                    logging.error(f"Failed to render guild widget {w_name}: {e}")

    fixed_widgets.sort(key=lambda x: x["order"])
    floating_widgets.sort(key=lambda x: x["order"])
    grid_widgets.sort(key=lambda x: x["order"])

    rendered_guild_widgets = [
        Div(c["component"], style=f"grid-column: span {c['span']};", cls="h-full") for c in grid_widgets
    ]

    guild_widgets = Div(
        Div(
            H2("Guild Admin Widgets", cls="text-2xl font-bold"),
            A(
                I(cls="fa-solid fa-pen-to-square mr-1"),
                "Edit Layout",
                href=f"/dashboard/{guild_id}/layout",
                cls="btn btn-sm btn-ghost text-info",
            ),
            cls="flex justify-between items-center mb-4",
        ),
        Div(*rendered_guild_widgets, cls="grid grid-cols-12 gap-6")
        if rendered_guild_widgets
        else P("No guild admin widgets enabled. Click 'Edit Layout' to configure."),
        cls="mb-8 mt-8",
    )

    access_roles_section = await _render_access_roles(guild_id)

    return DashboardPage(
        f"Dashboard: {guild['name']}",
        H1(f"Dashboard: {guild['name']}", cls="text-2xl font-extrabold mb-8"),
        access_roles_section,
        server_extensions,
        guild_widgets,
        auth=auth,
        guild_id=guild_id,
        guild_name=guild["name"],
        guild_icon=guild.get("icon"),
        fixed_widgets=fixed_widgets,
        floating_widgets=floating_widgets,
    )


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
                continue  # Public page hides admin and guild admin widgets

            if scope_id == SCOPE_ADMIN_DASHBOARD and not is_admin_widget:
                continue  # Admin dashboard only shows admin widgets

            if scope_id > 1 and not is_guild_admin_widget:
                continue  # Guild dashboard only shows guild admin widgets

            ws = settings.get(wname, {})
            pos_cfg = ws.get("position_config")

            # Lookup default position config of the widget function by its name
            default_pos = getattr(func, "default_pos", None) or getattr(func, "position_config", None)

            # Classify and normalize/default pos_cfg
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
    # Enabled widgets first (sorted by order), then disabled (sorted by order)
    # Force non-grid layout widgets to the bottom of the list of enabled widgets.
    # Update to push sidebar/floating widgets to the bottom by checking default_pos
    widgets.sort(
        key=lambda w: (
            not w["enabled"],
            w["enabled"]
            and w.get("default_pos") in ("left", "right", "bottom-right", "bottom-left", "top-right", "top-left"),
            w["order"],
        )
    )
    return widgets


def _humanize_widget_name(ext_name: str, raw_name: str) -> str:
    """Convert an internal widget function name to a human-readable label.

    If the widget function has a ``display_name`` attribute (set by dynamic
    widget generators like custom_content), that value is used directly.
    Otherwise, the raw function name is cleaned up by stripping common prefixes
    and replacing underscores with spaces.
    """
    # Check if the actual widget function carries a display_name attribute
    inspector = GadgetInspector()
    all_widgets = inspector.inspect_widgets()
    for func in all_widgets.get(ext_name, []):
        if getattr(func, "__name__", None) == raw_name:
            display = getattr(func, "display_name", None)
            if display:
                return display

    # Fallback: strip common prefixes and humanize
    name = raw_name
    name = name.removeprefix("widget_")
    name = name.replace("_", " ").strip()
    return name.title() if name else raw_name


def _render_layout_editor(widgets: list[dict], scope_id: int):
    """Render the layout editor table + live preview as an HTMX fragment."""

    # Determine target route based on scope for clarity, though we use same update/move routes
    # We just need to pass scope_id

    inspector = GadgetInspector()
    all_widgets_by_ext = inspector.inspect_widgets()
    widget_defaults = {}
    for _ext_name, widget_funcs in all_widgets_by_ext.items():
        for func in widget_funcs:
            wname = get_widget_name(func)
            if wname:
                widget_defaults[wname] = getattr(func, "default_pos", None) or getattr(func, "position_config", None)

    # Check for position collisions among enabled sidebar/floating widgets using normalized positions
    active_positions = {}
    for w in widgets:
        if w.get("enabled"):
            wname = w["widget"]
            default_pos = w.get("default_pos")
            if default_pos is None:
                default_pos = widget_defaults.get(wname)
            if default_pos is None:
                default_pos = w.get("position_config")
            pos_cfg = w.get("position_config")

            # Normalize pos_cfg
            if default_pos in ("left", "right"):
                if pos_cfg != "right":
                    pos_cfg = "left"
            elif default_pos in ("bottom-right", "bottom-left", "top-right", "top-left"):
                if pos_cfg not in ("bottom-right", "bottom-left", "top-right", "top-left"):
                    pos_cfg = "bottom-right"
            else:
                pos_cfg = None

            if pos_cfg:
                active_positions[pos_cfg] = active_positions.get(pos_cfg, 0) + 1

    collisions = [pos for pos, count in active_positions.items() if count > 1]
    warning_banner = None
    if collisions:
        pos_names = {
            "left": "Left Sidebar",
            "right": "Right Sidebar",
            "bottom-right": "Bottom Right",
            "bottom-left": "Bottom Left",
            "top-right": "Top Right",
            "top-left": "Top Left",
        }
        collision_labels = [pos_names.get(pos, pos) for pos in collisions]
        warning_banner = Div(
            Span(
                f"⚠️ Position Conflict: Multiple widgets are active in: {', '.join(collision_labels)}. They may overlap.",
                cls="font-semibold",
            ),
            cls="alert alert-warning mb-4",
        )

    rows = []
    for idx, w in enumerate(widgets):
        label = f"{w['ext'].replace('_', ' ').title()}: {_humanize_widget_name(w['ext'], w['widget'])}"
        wname = w["widget"]
        default_pos = w.get("default_pos")
        if default_pos is None:
            default_pos = widget_defaults.get(wname)
        if default_pos is None:
            default_pos = w.get("position_config")
        pos_cfg = w.get("position_config")

        # Classify each widget and normalize/default pos_cfg
        if default_pos in ("left", "right"):
            if pos_cfg != "right":
                pos_cfg = "left"
            widget_type = "Sidebar"
            config_td = Td(
                Form(
                    Select(
                        Option("Left Sidebar", value="left", selected=(pos_cfg == "left")),
                        Option("Right Sidebar", value="right", selected=(pos_cfg == "right")),
                        name="value",
                        cls="select select-sm select-bordered",
                    ),
                    Hidden(name="ext", value=w["ext"]),
                    Hidden(name="widget", value=w["widget"]),
                    Hidden(name="field", value="position_config"),
                    Hidden(name="scope_id", value=str(scope_id)),
                    hx_post="/admin/layout/update",
                    hx_trigger="change",
                    hx_target="#layout-editor",
                    hx_swap="innerHTML",
                )
            )
        elif default_pos in ("bottom-right", "bottom-left", "top-right", "top-left"):
            if pos_cfg not in ("bottom-right", "bottom-left", "top-right", "top-left"):
                pos_cfg = "bottom-right"
            widget_type = "Floating"
            config_td = Td(
                Form(
                    Select(
                        Option("Bottom Right", value="bottom-right", selected=(pos_cfg == "bottom-right")),
                        Option("Bottom Left", value="bottom-left", selected=(pos_cfg == "bottom-left")),
                        Option("Top Right", value="top-right", selected=(pos_cfg == "top-right")),
                        Option("Top Left", value="top-left", selected=(pos_cfg == "top-left")),
                        name="value",
                        cls="select select-sm select-bordered",
                    ),
                    Hidden(name="ext", value=w["ext"]),
                    Hidden(name="widget", value=w["widget"]),
                    Hidden(name="field", value="position_config"),
                    Hidden(name="scope_id", value=str(scope_id)),
                    hx_post="/admin/layout/update",
                    hx_trigger="change",
                    hx_target="#layout-editor",
                    hx_swap="innerHTML",
                )
            )
        else:
            widget_type = "Grid"
            config_td = Td(
                Form(
                    Select(
                        *[Option(f"{n} Columns", value=str(n), selected=(n == w["span"])) for n in range(1, 13)],
                        name="value",
                        cls="select select-sm select-bordered",
                    ),
                    Hidden(name="ext", value=w["ext"]),
                    Hidden(name="widget", value=w["widget"]),
                    Hidden(name="field", value="column_span"),
                    Hidden(name="scope_id", value=str(scope_id)),
                    hx_post="/admin/layout/update",
                    hx_trigger="change",
                    hx_target="#layout-editor",
                    hx_swap="innerHTML",
                )
            )

        type_td = Td(widget_type)
        is_fixed_or_floating = default_pos in ("left", "right", "bottom-right", "bottom-left", "top-right", "top-left")

        rows.append(
            Tr(
                # Widget name
                Td(label, cls="font-semibold"),
                # Enabled toggle
                Td(
                    Form(
                        Input(
                            type="checkbox",
                            name="enabled",
                            value="on",
                            checked=w["enabled"],
                            cls="checkbox checkbox-sm checkbox-primary",
                        ),
                        Hidden(name="ext", value=w["ext"]),
                        Hidden(name="widget", value=w["widget"]),
                        Hidden(name="field", value="is_enabled"),
                        Hidden(name="scope_id", value=str(scope_id)),
                        hx_post="/admin/layout/update",
                        hx_trigger="change",
                        hx_target="#layout-editor",
                        hx_swap="innerHTML",
                    )
                ),
                # Widget Type
                type_td,
                # Widget Config
                config_td,
                # Reorder buttons
                Td(
                    ""
                    if is_fixed_or_floating
                    else Div(
                        Form(
                            Hidden(name="ext", value=w["ext"]),
                            Hidden(name="widget", value=w["widget"]),
                            Hidden(name="direction", value="up"),
                            Hidden(name="scope_id", value=str(scope_id)),
                            Button(I(cls="fa-solid fa-arrow-up"), cls="btn btn-ghost btn-xs", disabled=(idx == 0)),
                            hx_post="/admin/layout/move",
                            hx_target="#layout-editor",
                            hx_swap="innerHTML",
                        ),
                        Form(
                            Hidden(name="ext", value=w["ext"]),
                            Hidden(name="widget", value=w["widget"]),
                            Hidden(name="direction", value="down"),
                            Hidden(name="scope_id", value=str(scope_id)),
                            Button(
                                I(cls="fa-solid fa-arrow-down"),
                                cls="btn btn-ghost btn-xs",
                                disabled=(idx == len(widgets) - 1),
                            ),
                            hx_post="/admin/layout/move",
                            hx_target="#layout-editor",
                            hx_swap="innerHTML",
                        ),
                        cls="flex gap-1",
                    )
                ),
            )
        )

    table_content = Div(
        Table(
            Thead(
                Tr(
                    Th("Widget"),
                    Th("Enabled"),
                    Th("Widget Type"),
                    Th("Widget Config"),
                    Th("Order"),
                )
            ),
            Tbody(*rows),
            cls="table table-zebra w-full",
        ),
        cls="overflow-x-auto",
    )

    if scope_id > 1:
        restore_form = Form(
            Hidden(name="scope_id", value=str(scope_id)),
            Button(
                I(cls="fa-solid fa-rotate-left mr-1"),
                "Restore Default Layout",
                cls="btn btn-outline btn-warning btn-xs",
                hx_confirm="Are you sure you want to restore the default layout? All custom positioning and sizing changes will be lost.",
            ),
            hx_post="/admin/layout/restore",
            hx_target="#layout-editor",
            hx_swap="innerHTML",
        )
        card_title = Div(
            H3("Widget Configuration", cls="card-title"),
            restore_form,
            cls="flex justify-between items-center w-full",
        )
    else:
        card_title = "Widget Configuration"

    table_card = Card(
        card_title,
        table_content,
    )

    # Live preview: shows widgets in a 12-column CSS grid
    preview_items = []
    for w in widgets:
        wname = w["widget"]
        default_pos = w.get("default_pos")
        if default_pos is None:
            default_pos = widget_defaults.get(wname)
        if default_pos is None:
            default_pos = w.get("position_config")
        if default_pos in ("left", "right", "bottom-right", "bottom-left", "top-right", "top-left"):
            continue  # Exclude from main grid live preview
        opacity = "opacity-100" if w["enabled"] else "opacity-30"
        # Styling widget boxes as mini-cards
        preview_items.append(
            Div(
                Div(
                    H5(w["ext"].replace("_", " ").title(), cls="font-bold text-xs opacity-70"),
                    Div(_humanize_widget_name(w["ext"], w["widget"]), cls="text-sm font-semibold truncate"),
                    cls="card-body p-3 text-center",
                ),
                cls=f"card bg-base-100 shadow-sm border border-base-content/20 {opacity}",
                style=f"grid-column: span {w['span']};",
            )
        )

    preview_section = Div(
        H3("Live Preview", cls="text-lg font-bold mb-4 ml-1 opacity-80"),
        Div(
            *preview_items,
            cls="grid grid-cols-12 gap-4",
        ),
        cls="mt-8",
    )

    children = []
    if warning_banner:
        children.append(warning_banner)
    children.extend([table_card, preview_section])
    return Div(*children)


@dashboard_router("/admin/layout")
def layout_editor(sess):
    """Page for editing the PUBLIC homepage widget layout."""
    auth = sess.get("auth", {})
    widgets = _get_ordered_widgets(SCOPE_PUBLIC)

    return DashboardPage(
        "Edit Public Layout",
        Div(
            H1("Edit Public Layout", cls="text-3xl font-extrabold mb-6"),
            P(
                "Configure which widgets appear on the public homepage, their width, and display order.",
                cls="mb-8 opacity-80",
            ),
            Div(
                _render_layout_editor(widgets, SCOPE_PUBLIC),
                id="layout-editor",
            ),
        ),
        auth=auth,
        guild_id=None,
        guild_name=None,
        fixed_widgets=None,
        floating_widgets=None,
    )


@dashboard_router("/admin/layout/admin")
def admin_layout_editor(sess):
    """Page for editing the ADMIN dashboard widget layout."""
    auth = sess.get("auth", {})
    widgets = _get_ordered_widgets(SCOPE_ADMIN_DASHBOARD)

    return DashboardPage(
        "Edit Admin Layout",
        Div(
            H1("Edit Admin Layout", cls="text-3xl font-extrabold mb-6"),
            P(
                "Configure which widgets appear on the Admin Dashboard, their width, and display order.",
                cls="mb-8 opacity-80",
            ),
            Div(
                _render_layout_editor(widgets, SCOPE_ADMIN_DASHBOARD),
                id="layout-editor",
            ),
        ),
        auth=auth,
        guild_id=None,
        guild_name=None,
        fixed_widgets=None,
        floating_widgets=None,
    )


@dashboard_router("/dashboard/{guild_id:int}/layout")
async def guild_layout_editor(guild_id: int, sess):
    """Page for editing a GUILD dashboard widget layout."""
    auth = sess.get("auth", {})
    user_access_token = auth.get("token_data", {}).get("access_token")
    if not user_access_token:
        return Titled("Error", P("Could not retrieve necessary tokens."))

    try:
        user_id = int(auth.get("id"))
        admin_guilds = await get_admin_guilds(user_access_token, user_id)
        guild = admin_guilds.get(str(guild_id), {"name": "Unknown Server"})
    except Exception as e:
        return Titled("Error", P(f"Failed to fetch guild information: {e}"))

    widgets = _get_ordered_widgets(guild_id)

    return DashboardPage(
        f"Edit Layout: {guild['name']}",
        Div(
            H1(f"Edit Layout: {guild['name']}", cls="text-3xl font-extrabold mb-6"),
            P(
                "Configure which widgets appear on this Guild Dashboard, their width, and display order.",
                cls="mb-8 opacity-80",
            ),
            Div(
                _render_layout_editor(widgets, guild_id),
                id="layout-editor",
            ),
            A("Back to Dashboard", href=f"/dashboard/{guild_id}", role="button", cls="secondary mt-8 inline-block"),
        ),
        auth=auth,
        guild_id=guild_id,
        guild_name=guild["name"],
        guild_icon=guild.get("icon"),
        fixed_widgets=None,
        floating_widgets=None,
    )


@dashboard_router("/admin/layout/update", methods=["POST"])
async def layout_update(req):
    """Handles updating a single widget setting (enabled or column_span)."""
    form = await req.form()
    ext = form.get("ext")
    widget = form.get("widget")
    field = form.get("field")
    # form.get returns '' for falsy values like 0; default to SCOPE_PUBLIC
    raw_scope = form.get("scope_id", "")
    scope_id = int(raw_scope) if raw_scope else SCOPE_PUBLIC

    if field == "is_enabled":
        value = form.get("enabled") == "on"
    elif field == "column_span":
        value = int(form.get("value", 4))
    elif field == "position_config":
        value = form.get("value")
    else:
        return P("Unknown field", cls="text-error")

    update_widget_setting(scope_id, ext, widget, field, value)

    # After toggling enabled, re-persist order so disabled widgets stay at bottom
    widgets = _get_ordered_widgets(scope_id)
    if field == "is_enabled":
        for new_order, w in enumerate(widgets):
            update_widget_setting(scope_id, w["ext"], w["widget"], "display_order", new_order)
        widgets = _get_ordered_widgets(scope_id)
    return _render_layout_editor(widgets, scope_id)


@dashboard_router("/admin/layout/move", methods=["POST"])
async def layout_move(req):
    """Handles reordering a widget up or down."""
    form = await req.form()
    ext = form.get("ext")
    widget_name = form.get("widget")
    direction = form.get("direction")
    # form.get returns '' for falsy values like 0; default to SCOPE_PUBLIC
    raw_scope = form.get("scope_id", "")
    scope_id = int(raw_scope) if raw_scope else SCOPE_PUBLIC

    widgets = _get_ordered_widgets(scope_id)

    # Find the widget's current index
    idx = next((i for i, w in enumerate(widgets) if w["ext"] == ext and w["widget"] == widget_name), None)
    if idx is None:
        return _render_layout_editor(widgets, scope_id)

    # Swap with neighbor
    if direction == "up" and idx > 0:
        widgets[idx], widgets[idx - 1] = widgets[idx - 1], widgets[idx]
    elif direction == "down" and idx < len(widgets) - 1:
        widgets[idx], widgets[idx + 1] = widgets[idx + 1], widgets[idx]

    # Persist new order
    for new_order, w in enumerate(widgets):
        update_widget_setting(scope_id, w["ext"], w["widget"], "display_order", new_order)

    widgets = _get_ordered_widgets(scope_id)
    return _render_layout_editor(widgets, scope_id)


@dashboard_router("/admin/layout/restore", methods=["POST"])
async def layout_restore(req):
    """Handles restoring the default widget layout for a given scope/guild."""
    form = await req.form()
    raw_scope = form.get("scope_id", "")
    scope_id = int(raw_scope) if raw_scope else SCOPE_PUBLIC

    from app.ui.helpers import restore_default_widget_settings

    restore_default_widget_settings(scope_id)

    widgets = _get_ordered_widgets(scope_id)
    return _render_layout_editor(widgets, scope_id)


async def _render_access_roles(guild_id: int):
    # Fetch roles from bot API
    guild_roles = []
    try:
        async with get_internal_api_client() as client:
            resp = await client.get(f"http://127.0.0.1:8001/guilds/{guild_id}/roles", timeout=2.0)
            if resp.status_code == 200:
                guild_roles = resp.json().get("roles", [])
    except Exception as e:
        logging.error(f"Failed to fetch guild roles: {e}")

    from sqlmodel import Session, select

    from app.common.alchemy import init_connection_engine
    from app.db.models import DashboardAccessRole

    engine = init_connection_engine()
    with Session(engine) as session:
        stmt = select(DashboardAccessRole).where(DashboardAccessRole.guild_id == guild_id)
        saved_roles = session.exec(stmt).all()
        saved_role_ids = {str(r.role_id) for r in saved_roles}

    active_role_badges = []
    for r in saved_roles:
        role_name = str(r.role_id)
        role_info = next((gr for gr in guild_roles if gr["id"] == str(r.role_id)), None)
        if role_info:
            role_name = role_info["name"]

        badge = Div(
            Span(role_name, cls="mr-2"),
            Form(
                Hidden(name="role_id", value=str(r.role_id)),
                Button(
                    I(cls="fa-solid fa-xmark"),
                    cls="btn btn-ghost btn-xs text-error p-0 border-0 bg-transparent shadow-none hover:bg-transparent",
                ),
                hx_post=f"/dashboard/{guild_id}/access-roles/remove",
                hx_target="#access-roles-container",
                hx_swap="outerHTML",
                cls="inline flex items-center",
            ),
            cls="badge badge-primary gap-1 py-3 px-3",
        )
        active_role_badges.append(badge)

    available_roles = [r for r in guild_roles if r["id"] not in saved_role_ids]
    add_role_form = Form(
        Select(
            Option("Select a role...", value="", disabled=True, selected=True),
            *[Option(r["name"], value=r["id"]) for r in available_roles],
            name="role_id",
            cls="select select-bordered select-sm w-full max-w-xs mr-2",
        ),
        Button("Grant Access", cls="btn btn-primary btn-sm"),
        hx_post=f"/dashboard/{guild_id}/access-roles/add",
        hx_target="#access-roles-container",
        hx_swap="outerHTML",
        cls="mt-4 flex items-center",
        id="add-role-form",
    )

    return Div(
        H3("Dashboard Access Roles", cls="text-xl font-bold mb-2"),
        P("Users with these roles can access this server's dashboard.", cls="text-sm opacity-80 mb-4"),
        Div(*active_role_badges, cls="flex gap-2 flex-wrap mb-4")
        if active_role_badges
        else P("No additional roles granted.", cls="text-sm italic opacity-60"),
        add_role_form
        if available_roles
        else P("All available roles have been granted access.", cls="text-sm text-success mt-4"),
        id="access-roles-container",
        cls="p-4 bg-base-200 rounded-lg shadow-inner mb-8",
    )


@dashboard_router("/dashboard/{guild_id:int}/access-roles/add", methods=["POST"])
async def add_access_role(guild_id: int, req, sess):
    auth = sess.get("auth", {})
    user_access_token = auth.get("token_data", {}).get("access_token")
    if not user_access_token:
        return P("Unauthorized", cls="text-error")

    # Authorization is handled in auth_before middleware.

    form = await req.form()
    role_id_str = form.get("role_id")
    if role_id_str:
        try:
            role_id = int(role_id_str)
            from sqlmodel import Session

            from app.common.alchemy import init_connection_engine
            from app.db.models import DashboardAccessRole

            engine = init_connection_engine()
            with Session(engine) as session:
                new_role = DashboardAccessRole(guild_id=guild_id, role_id=role_id)
                session.add(new_role)
                session.commit()
        except ValueError:
            pass

    return await _render_access_roles(guild_id)


@dashboard_router("/dashboard/{guild_id:int}/access-roles/remove", methods=["POST"])
async def remove_access_role(guild_id: int, req, sess):
    auth = sess.get("auth", {})
    user_access_token = auth.get("token_data", {}).get("access_token")
    if not user_access_token:
        return P("Unauthorized", cls="text-error")

    # Authorization is handled in auth_before middleware.

    form = await req.form()
    role_id_str = form.get("role_id")
    if role_id_str:
        try:
            role_id = int(role_id_str)
            from sqlmodel import Session, select

            from app.common.alchemy import init_connection_engine
            from app.db.models import DashboardAccessRole

            engine = init_connection_engine()
            with Session(engine) as session:
                stmt = select(DashboardAccessRole).where(
                    DashboardAccessRole.guild_id == guild_id, DashboardAccessRole.role_id == role_id
                )
                role = session.exec(stmt).first()
                if role:
                    session.delete(role)
                    session.commit()
        except ValueError:
            pass

    return await _render_access_roles(guild_id)


@dashboard_router("/dashboard/{guild_id:int}/lockdown", methods=["POST"])
async def lockdown_route(guild_id: int):
    """
    Emergency lockdown route.
    """
    return Div(
        Span("🚨 Emergency Lockdown Initiated! Channels are being locked down.", cls="font-bold"),
        cls="alert alert-error shadow-lg flex items-center gap-2",
    )


@dashboard_router("/dashboard/{guild_id:int}/toggle-nav", methods=["POST"])
async def toggle_nav_route(guild_id: int, req, sess):
    """
    Handles toggling user visibility preferences (updates UserSetting in the database).
    """
    auth = sess.get("auth", {})
    user_id_str = auth.get("id")
    if not user_id_str:
        return Response("Unauthorized", status_code=401)

    try:
        user_id = int(user_id_str)
    except ValueError:
        return Response("Invalid User ID", status_code=400)

    # Read parameters from query parameters or form data
    show_topbar_param = req.query_params.get("show_topbar")

    try:
        form_data = await req.form()
        if show_topbar_param is None:
            show_topbar_param = form_data.get("show_topbar")
    except Exception:  # noqa: S110
        pass

    from sqlmodel import Session

    from app.common.alchemy import init_connection_engine
    from app.db.models import UserSetting

    engine = init_connection_engine()
    with Session(engine) as session:
        user_setting = session.get(UserSetting, user_id)
        if not user_setting:
            user_setting = UserSetting(user_id=user_id)

        if show_topbar_param is not None:
            user_setting.show_topbar = show_topbar_param.lower() in ("true", "1", "yes", "on")

        session.add(user_setting)
        session.commit()

    return Response(headers={"HX-Refresh": "true"})


@dashboard_router("/dashboard/{guild_id:int}/auditor-settings", methods=["POST"])
async def post_auditor_settings(guild_id: int, req):
    """Parses lowest admin role and staff/announcement channels, validates, and saves in DB."""
    import json

    from sqlmodel import Session, select

    from app.common.alchemy import init_connection_engine
    from app.db.models import DiscordAuditorConfig

    form = await req.form()

    # staff_separator_role_id
    role_id_raw = form.get("staff_separator_role_id")
    staff_separator_role_id = None
    if role_id_raw:
        try:
            staff_separator_role_id = int(role_id_raw)
        except ValueError:
            pass

    # staff_channel_ids
    staff_ids_raw = form.getlist("staff_channel_ids")
    staff_channel_ids = []
    if not staff_ids_raw:
        staff_ids_fallback = form.get("staff_channel_ids", "")
        if isinstance(staff_ids_fallback, str):
            staff_ids_raw = [staff_ids_fallback]
    for raw_val in staff_ids_raw:
        if not raw_val:
            continue
        for part in str(raw_val).split(","):
            part_clean = part.strip()
            if part_clean:
                try:
                    staff_channel_ids.append(int(part_clean))
                except ValueError:
                    pass

    # announcement_channel_ids
    ann_ids_raw = form.getlist("announcement_channel_ids")
    ann_channel_ids = []
    if not ann_ids_raw:
        ann_ids_fallback = form.get("announcement_channel_ids", "")
        if isinstance(ann_ids_fallback, str):
            ann_ids_raw = [ann_ids_fallback]
    for raw_val in ann_ids_raw:
        if not raw_val:
            continue
        for part in str(raw_val).split(","):
            part_clean = part.strip()
            if part_clean:
                try:
                    ann_channel_ids.append(int(part_clean))
                except ValueError:
                    pass

    engine = init_connection_engine()
    with Session(engine) as session:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        if not config:
            config = DiscordAuditorConfig(guild_id=guild_id)
            session.add(config)

        config.staff_separator_role_id = staff_separator_role_id
        config.staff_channel_ids = json.dumps(staff_channel_ids)
        config.announcement_channel_ids = json.dumps(ann_channel_ids)
        session.commit()

    from app.extensions.utilities.widget import SecurityRuleEngine

    SecurityRuleEngine.invalidate(guild_id)

    return Response(
        content='<div class="alert alert-success mt-4">✅ Auditor settings updated successfully!</div>',
        headers={"HX-Refresh": "true"},
    )


@dashboard_router("/dashboard/{guild_id:int}/alerts-list", methods=["GET"])
async def get_alerts_list(guild_id: int, req, category: str = "all"):
    """Evaluates rules, filters alerts by category, and returns the HTMX list segment."""
    from sqlmodel import Session

    from app.common.alchemy import init_connection_engine
    from app.extensions.utilities.widget import SecurityRuleEngine, _render_alerts_list

    category = req.query_params.get("category", "all")

    engine = init_connection_engine()
    with Session(engine) as session:
        evaluation = SecurityRuleEngine.evaluate(guild_id, session)
        alerts = evaluation["alerts"]

    active_hashes = {a.get("alert_hash", "") for a in alerts}

    if category != "all":
        alerts = [a for a in alerts if a.get("category", "").lower() == category.lower()]

    return _render_alerts_list(alerts, guild_id, active_hashes=active_hashes)


@dashboard_router("/dashboard/{guild_id:int}/rules-info", methods=["GET"])
async def get_rules_info(guild_id: int):
    """Returns a modal explaining all security rules in detail."""
    from app.extensions.utilities.widget import get_security_rules_modal

    return get_security_rules_modal(guild_id)


@dashboard_router("/dashboard/{guild_id:int}/alerts/override-confirm", methods=["GET"])
async def get_override_confirm_modal(guild_id: int, req):
    """Returns confirmation modal for overriding a specific alert."""
    from app.extensions.utilities.widget import get_override_confirm_modal_html

    alert_hash = req.query_params.get("alert_hash", "")
    return get_override_confirm_modal_html(guild_id, alert_hash)


@dashboard_router("/dashboard/{guild_id:int}/alerts/override", methods=["POST"])
async def post_alert_override(guild_id: int, req):
    """Saves a security alert override to the database and refreshes the page."""
    from sqlmodel import Session

    from app.common.alchemy import init_connection_engine
    from app.db.models import SecurityAlertOverride
    from app.extensions.utilities.widget import SecurityRuleEngine

    form = await req.form()
    alert_hash = form.get("alert_hash")
    rule = form.get("rule")
    category = form.get("category")
    message = form.get("message")
    details = form.get("details", "")
    comment = form.get("comment", "")

    if not alert_hash:
        return Response(content="Missing alert hash", status_code=400)

    engine = init_connection_engine()
    with Session(engine) as session:
        # Check if already exists
        existing = session.exec(
            select(SecurityAlertOverride).where(
                SecurityAlertOverride.guild_id == guild_id, SecurityAlertOverride.alert_hash == alert_hash
            )
        ).first()
        if not existing:
            override = SecurityAlertOverride(
                guild_id=guild_id,
                alert_hash=alert_hash,
                rule=rule,
                category=category,
                message=message,
                details=details,
                comment=comment,
            )
            session.add(override)
            session.commit()

    SecurityRuleEngine.invalidate(guild_id)

    return Response(
        headers={"HX-Refresh": "true"},
    )


@dashboard_router("/dashboard/{guild_id:int}/alerts/override/remove", methods=["POST"])
async def post_alert_override_remove(guild_id: int, req):
    """Deletes a security alert override and refreshes the page."""
    from sqlmodel import Session

    from app.common.alchemy import init_connection_engine
    from app.db.models import SecurityAlertOverride
    from app.extensions.utilities.widget import SecurityRuleEngine

    alert_hash = req.query_params.get("alert_hash")
    if not alert_hash:
        return Response(content="Missing alert hash", status_code=400)

    engine = init_connection_engine()
    with Session(engine) as session:
        override = session.exec(
            select(SecurityAlertOverride).where(
                SecurityAlertOverride.guild_id == guild_id, SecurityAlertOverride.alert_hash == alert_hash
            )
        ).first()
        if override:
            session.delete(override)
            session.commit()

    SecurityRuleEngine.invalidate(guild_id)

    return Response(
        headers={"HX-Refresh": "true"},
    )


@dashboard_router("/dashboard/{guild_id:int}/scan", methods=["POST"])
async def dashboard_scan_guild(guild_id: int):
    import os

    bot_port = int(os.getenv("POWERCORD_BOT_API_PORT", 8001))
    try:
        async with get_internal_api_client() as client:
            resp = await client.post(f"http://127.0.0.1:{bot_port}/guilds/{guild_id}/scan")
            if resp.status_code != 200:
                logging.error(f"Failed to scan guild {guild_id}: Bot returned status {resp.status_code}")
    except Exception as e:
        logging.error(f"Failed to scan guild {guild_id}: {e}")

    from app.extensions.utilities.widget import SecurityRuleEngine

    SecurityRuleEngine.invalidate(guild_id)

    return Response(headers={"HX-Refresh": "true"})


@dashboard_router("/dashboard/{guild_id:int}/ping-bot", methods=["GET"])
async def dashboard_ping_bot(guild_id: int):
    import os

    bot_port = int(os.getenv("POWERCORD_BOT_API_PORT", 8001))
    latency = None
    try:
        async with get_internal_api_client() as client:
            resp = await client.get(f"http://127.0.0.1:{bot_port}/stats", timeout=1.5)
            if resp.status_code == 200:
                stats = resp.json()
                latency = stats.get("bot", {}).get("latency")
    except Exception as e:
        logging.error(f"Failed to ping bot stats: {e}")

    if latency is not None:
        text = f"🟢 Connected ({latency}ms)"
        cls_color = "badge-success text-success-content"
    else:
        text = "🔴 Disconnected"
        cls_color = "badge-error text-error-content"

    return Span(text, id=f"bot-latency-display-{guild_id}", cls=f"badge {cls_color} badge-sm")
