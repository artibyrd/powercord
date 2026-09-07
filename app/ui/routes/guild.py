# mypy: ignore-errors
from __future__ import annotations

import logging

from fasthtml.common import *
from fasthtml.core import APIRouter
from starlette.responses import Response

from app.bot.internal_server import get_bot_api_url
from app.common.extension_hooks import run_hook, supports_delete_data
from app.common.extension_loader import GadgetInspector
from app.common.extension_manager import get_installed_extensions
from app.ui.dashboard.api_keys import _render_self_service_keys
from app.ui.dashboard.grid import format_extension_title, server_extension_card
from app.ui.dashboard.roles import (
    _check_guild_admin,
    _render_access_roles,
    _render_api_user_role,
)
from app.ui.helpers import (
    get_admin_guilds,
    get_guild_cogs,
    get_guild_sprockets,
    get_guild_widgets,
    get_internal_api_client,
    get_widget_name,
    get_widget_settings,
    is_dashboard_admin,
    is_gadget_enabled,
    update_guild_extension_setting,
)
from app.ui.page import DashboardPage

guild_router = APIRouter()


@guild_router("/dashboard/{guild_id:int}/extensions/{extension_name}/details", methods=["GET"])
async def server_extension_details_route(guild_id: int, extension_name: str, req):
    """Returns a modal with the extension details for a specific server dashboard."""
    from app.ui.helpers import get_extension_details_modal

    auth_data = req.session.get("auth", {})
    token_data = auth_data.get("token_data", {})
    access_token = token_data.get("access_token")
    return get_extension_details_modal(extension_name, access_token=access_token)


@guild_router("/dashboard/{guild_id:int}/extensions/{extension_name}/confirm-delete", methods=["GET"])
async def confirm_delete_data_route(guild_id: int, extension_name: str, req):
    """Returns a confirmation modal before deleting extension data for a guild."""
    if not await _check_guild_admin(guild_id, req):
        return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    modal_content = Dialog(
        Div(
            H3(
                I(cls="fa-solid fa-triangle-exclamation mr-2 text-warning"),
                "Delete Server Data",
                cls="font-bold text-lg",
            ),
            P(
                "This will permanently delete all ",
                Strong(format_extension_title(extension_name)),
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
        Form(method="dialog", cls="modal-backdrop", children=[Button("close")]),
        id="modal-container",
        cls="modal modal-open",
    )
    return modal_content


@guild_router("/dashboard/{guild_id:int}/extensions/{extension_name}/delete-data", methods=["POST"])
async def delete_server_data_route(guild_id: int, extension_name: str, req):
    """Executes deletion of all extension-specific data for a guild."""
    if not await _check_guild_admin(guild_id, req):
        return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    if not supports_delete_data(extension_name):
        return P(f"Extension '{extension_name}' does not support data deletion.", cls="text-error")

    run_hook(extension_name, "delete_guild_data", guild_id=guild_id)
    logging.info(f"Deleted server data for extension '{extension_name}' on guild {guild_id}.")

    inspector = GadgetInspector()
    all_extensions = inspector.inspect_extensions()
    gadgets = all_extensions.get(extension_name, [])
    enabled_cogs = get_guild_cogs(guild_id)
    enabled_sprockets = get_guild_sprockets(guild_id)
    enabled_widgets = get_guild_widgets(guild_id)

    card = server_extension_card(guild_id, extension_name, gadgets, enabled_cogs, enabled_sprockets, enabled_widgets)
    close_modal = Dialog(id="modal-container", hx_swap_oob="true")
    toast = Div(
        Div(
            Span(f"Deleted data for {format_extension_title(extension_name)}.", cls="font-semibold"),
            cls="alert alert-success shadow-lg",
        ),
        cls="toast toast-end toast-bottom z-50",
        id="toast-container",
        hx_swap_oob="afterbegin",
    )
    return card, close_modal, toast


@guild_router("/dashboard/{guild_id:int}/extensions/toggle", methods=["POST"])
async def toggle_server_extension(guild_id: int, req):
    """Handles toggling an extension on/off for a specific server."""
    if not await _check_guild_admin(guild_id, req):
        return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    form_data = await req.form()
    extension_name = form_data.get("extension_name")
    is_enabled = form_data.get("enabled") == "on"

    logging.info(f"Toggle server: Guild={guild_id} Ext={extension_name} Enabled={is_enabled}")

    inspector = GadgetInspector()
    all_extensions = inspector.inspect_extensions()
    gadgets = all_extensions.get(extension_name, [])

    global_cogs = get_guild_cogs(0)
    global_sprockets = get_guild_sprockets(0)
    global_widgets = get_guild_widgets(0)

    server_gadgets = []
    if "cog" in gadgets and extension_name in global_cogs:
        server_gadgets.append("cog")
    if "sprocket" in gadgets and extension_name in global_sprockets:
        server_gadgets.append("sprocket")
    if "widget" in gadgets and extension_name in global_widgets:
        server_gadgets.append("widget")

    for g_type in server_gadgets:
        update_guild_extension_setting(guild_id, extension_name, g_type, is_enabled)

    enabled_cogs = get_guild_cogs(guild_id)
    enabled_sprockets = get_guild_sprockets(guild_id)
    enabled_widgets = get_guild_widgets(guild_id)

    return server_extension_card(
        guild_id, extension_name, server_gadgets, enabled_cogs, enabled_sprockets, enabled_widgets
    )


@guild_router("/dashboard/{guild_id:int}")
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

    is_guild_admin = (
        guild.get("owner", False) or (int(guild.get("permissions", 0)) & (1 << 3)) != 0 or is_dashboard_admin(user_id)
    )

    inspector = GadgetInspector()
    all_extensions = inspector.inspect_extensions()

    if "powerloader" in all_extensions:
        del all_extensions["powerloader"]

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
                server_extension_card(
                    guild_id,
                    name,
                    server_gadgets,
                    enabled_cogs,
                    enabled_sprockets,
                    enabled_widgets,
                    disabled=not is_guild_admin,
                )
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

    edit_layout_btn = ""
    if is_guild_admin:
        edit_layout_btn = A(
            I(cls="fa-solid fa-pen-to-square mr-1"),
            "Edit Layout",
            href=f"/dashboard/{guild_id}/layout",
            cls="btn btn-sm btn-ghost text-info",
        )

    guild_widgets = Div(
        Div(
            H2("Guild Admin Widgets", cls="text-2xl font-bold"),
            edit_layout_btn,
            cls="flex justify-between items-center mb-4",
        ),
        Div(*rendered_guild_widgets, cls="grid grid-cols-12 gap-6")
        if rendered_guild_widgets
        else P(
            "No guild admin widgets enabled. Click 'Edit Layout' to configure."
            if is_guild_admin
            else "No guild admin widgets are currently enabled."
        ),
        cls="mb-8 mt-8",
    )

    access_roles_section = await _render_access_roles(guild_id) if is_guild_admin else Div()
    api_user_role_section = await _render_api_user_role(guild_id) if is_guild_admin else Div()

    roles_grid = (
        Div(access_roles_section, api_user_role_section, cls="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8")
        if is_guild_admin
        else Div()
    )

    has_api_user_role = False
    try:
        from sqlmodel import Session, select

        from app.common.alchemy import init_connection_engine
        from app.db.models import ApiUserRole

        engine = init_connection_engine()
        with Session(engine) as session:
            stmt = select(ApiUserRole).where(ApiUserRole.guild_id == guild_id)
            api_user_role = session.exec(stmt).first()

        if api_user_role:
            user_roles = set()
            async with get_internal_api_client() as client:
                resp = await client.get(get_bot_api_url(f"/user/{user_id}/guilds/{guild_id}/roles"), timeout=2.0)
                if resp.status_code == 200:
                    user_role_ids = resp.json().get("roles", [])
                    user_roles = {int(r) for r in user_role_ids}
            if int(api_user_role.role_id) in user_roles:
                has_api_user_role = True
    except Exception as e:
        logging.error(f"Failed to check API user role for guild {guild_id}: {e}")

    show_api_keys = is_guild_admin or has_api_user_role
    api_keys_section = await _render_self_service_keys(guild_id, user_id, sess) if show_api_keys else Div()

    server_extensions_section = server_extensions if is_guild_admin else Div()

    return DashboardPage(
        f"Dashboard: {guild['name']}",
        H1(f"Dashboard: {guild['name']}", cls="text-2xl font-extrabold mb-8"),
        roles_grid,
        server_extensions_section,
        api_keys_section,
        guild_widgets,
        auth=auth,
        guild_id=guild_id,
        guild_name=guild["name"],
        guild_icon=guild.get("icon"),
        fixed_widgets=fixed_widgets,
        floating_widgets=floating_widgets,
    )


@guild_router("/dashboard/{guild_id:int}/lockdown", methods=["POST"])
async def lockdown_route(guild_id: int):
    """Emergency lockdown route."""
    return Div(
        Span("🚨 Emergency Lockdown Initiated! Channels are being locked down.", cls="font-bold"),
        cls="alert alert-error shadow-lg flex items-center gap-2",
    )


@guild_router("/dashboard/{guild_id:int}/scan", methods=["POST"])
async def dashboard_scan_guild(guild_id: int):
    url = get_bot_api_url(f"/guilds/{guild_id}/scan")
    try:
        async with get_internal_api_client() as client:
            resp = await client.post(url)
            if resp.status_code != 200:
                logging.error(f"Failed to scan guild {guild_id}: Bot returned status {resp.status_code}")
    except Exception as e:
        logging.error(f"Failed to scan guild {guild_id}: {e}")

    from app.extensions.utilities.widget import SecurityRuleEngine

    SecurityRuleEngine.invalidate(guild_id)

    return Response(headers={"HX-Refresh": "true"})


@guild_router("/dashboard/{guild_id:int}/ping-bot", methods=["GET"])
async def dashboard_ping_bot(guild_id: int):
    url = get_bot_api_url("/stats")
    status_text = "🔴 Disconnected"
    cls_color = "badge-error text-error-content"
    try:
        async with get_internal_api_client() as client:
            resp = await client.get(url, timeout=2.0)
            if resp.status_code == 200:
                stats = resp.json()
                if isinstance(stats, dict) and "bot" in stats:
                    bot_info = stats.get("bot", {})
                    status_val = bot_info.get("status")
                    latency = bot_info.get("latency")
                    if status_val == "connected" and latency is not None:
                        status_text = f"🟢 Connected ({latency}ms)"
                        cls_color = "badge-success text-success-content"
                    elif status_val == "connecting":
                        status_text = "🟡 Connecting..."
                        cls_color = "badge-warning text-warning-content"
                    elif latency is not None:
                        status_text = f"🟢 Connected ({latency}ms)"
                        cls_color = "badge-success text-success-content"
                    elif status_val == "connected" or bot_info.get("is_ready"):
                        status_text = "🟢 Connected (Ready)"
                        cls_color = "badge-success text-success-content"
    except Exception as e:
        logging.debug(f"Failed to ping bot stats: {e}")

    return Span(status_text, id=f"bot-latency-display-{guild_id}", cls=f"badge {cls_color} badge-sm")


@guild_router("/dashboard/{guild_id:int}/alerts-list", methods=["GET"])
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


@guild_router("/dashboard/{guild_id:int}/rules-info", methods=["GET"])
async def get_rules_info(guild_id: int):
    """Returns a modal explaining all security rules in detail."""
    from app.extensions.utilities.widget import get_security_rules_modal

    return get_security_rules_modal(guild_id)


@guild_router("/dashboard/{guild_id:int}/alerts/override-confirm", methods=["GET"])
async def get_override_confirm_modal(guild_id: int, req):
    """Returns confirmation modal for overriding a specific alert."""
    from app.extensions.utilities.widget import get_override_confirm_modal_html

    alert_hash = req.query_params.get("alert_hash", "")
    return get_override_confirm_modal_html(guild_id, alert_hash)
