# mypy: ignore-errors
from __future__ import annotations

import logging
import sys
from pathlib import Path

import httpx
from fasthtml.common import *
from fasthtml.core import APIRouter

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


from app.common.extension_hooks import run_hook, supports_delete_data
from app.common.extension_loader import GadgetInspector
from app.ui.components import Card
from app.ui.helpers import (
    SCOPE_ADMIN_DASHBOARD,
    SCOPE_PUBLIC,
    get_admin_guilds,
    get_guild_cogs,
    get_guild_sprockets,
    get_guild_widgets,
    get_widget_name,
    get_widget_settings,
    is_gadget_enabled,
    notify_api_of_config_change,
    update_guild_extension_setting,
    update_widget_setting,
)
from app.ui.page import StandardPage


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

    return get_extension_details_modal(extension_name)


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

    enabled_cogs = get_guild_cogs(guild_id)
    enabled_sprockets = get_guild_sprockets(guild_id)
    enabled_widgets = get_guild_widgets(guild_id)

    global_cogs = get_guild_cogs(0)
    global_sprockets = get_guild_sprockets(0)
    global_widgets = get_guild_widgets(0)

    server_extension_cards = []
    for name, gadgets in all_extensions.items():
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

    guild_widget_configs = []

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
                    guild_widget_configs.append(
                        {
                            "component": func(guild_id),
                            "order": widget_setting.get("display_order", 99),
                            "span": widget_setting.get("column_span", 4),
                        }
                    )
                except Exception as e:
                    logging.error(f"Failed to render guild widget {w_name}: {e}")

    guild_widget_configs.sort(key=lambda x: x["order"])
    rendered_guild_widgets = [
        Div(c["component"], style=f"grid-column: span {c['span']};") for c in guild_widget_configs
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

    return StandardPage(
        f"Dashboard: {guild['name']}",
        H1(f"Dashboard: {guild['name']}", cls="text-2xl font-extrabold mb-8"),
        access_roles_section,
        server_extensions,
        guild_widgets,
        A("Back to Dashboard", href="/admin", role="button", cls="secondary mt-8 inline-block"),
        auth=auth,
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
            widgets.append(
                {
                    "ext": ext_name,
                    "widget": wname,
                    "enabled": ws.get("is_enabled", False),
                    "span": ws.get("column_span", 4),
                    "order": ws.get("display_order", 99),
                }
            )
    # Enabled widgets first (sorted by order), then disabled (sorted by order)
    widgets.sort(key=lambda w: (not w["enabled"], w["order"]))
    return widgets


def _render_layout_editor(widgets: list[dict], scope_id: int):
    """Render the layout editor table + live preview as an HTMX fragment."""

    # Determine target route based on scope for clarity, though we use same update/move routes
    # We just need to pass scope_id

    rows = []
    for idx, w in enumerate(widgets):
        label = f"{w['ext'].capitalize()}: {w['widget']}"
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
                # Column span selector
                Td(
                    Form(
                        Select(
                            *[Option(str(n), value=str(n), selected=(n == w["span"])) for n in range(1, 13)],
                            name="value",
                            cls="select select-sm select-bordered w-20",
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
                ),
                # Reorder buttons
                Td(
                    Div(
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
                    ),
                ),
            )
        )

    table_card = Card(
        "Widget Configuration",
        Div(
            Table(
                Thead(
                    Tr(
                        Th("Widget"),
                        Th("Enabled"),
                        Th("Columns (1-12)"),
                        Th("Order"),
                    )
                ),
                Tbody(*rows),
                cls="table table-zebra w-full",
            ),
            cls="overflow-x-auto",
        ),
    )

    # Live preview: shows widgets in a 12-column CSS grid
    preview_items = []
    for w in widgets:
        opacity = "opacity-100" if w["enabled"] else "opacity-30"
        # Styling widget boxes as mini-cards
        preview_items.append(
            Div(
                Div(
                    H5(w["ext"].capitalize(), cls="font-bold text-xs opacity-70"),
                    Div(w["widget"], cls="text-sm font-semibold truncate"),
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

    return Div(table_card, preview_section)


@dashboard_router("/admin/layout")
def layout_editor(sess):
    """Page for editing the PUBLIC homepage widget layout."""
    auth = sess.get("auth", {})
    widgets = _get_ordered_widgets(SCOPE_PUBLIC)

    return StandardPage(
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
    )


@dashboard_router("/admin/layout/admin")
def admin_layout_editor(sess):
    """Page for editing the ADMIN dashboard widget layout."""
    auth = sess.get("auth", {})
    widgets = _get_ordered_widgets(SCOPE_ADMIN_DASHBOARD)

    return StandardPage(
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

    return StandardPage(
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


async def _render_access_roles(guild_id: int):
    # Fetch roles from bot API
    guild_roles = []
    try:
        async with httpx.AsyncClient() as client:
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
