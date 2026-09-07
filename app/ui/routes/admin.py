# mypy: ignore-errors
from __future__ import annotations

import functools
import inspect
import logging

from fasthtml.common import *
from fasthtml.core import APIRouter

from app.common.extension_loader import GadgetInspector
from app.ui.components import Card
from app.ui.helpers import (
    SCOPE_ADMIN_DASHBOARD,
    get_guild_cogs,
    get_guild_sprockets,
    get_guild_widgets,
    get_internal_api_client,
    get_widget_name,
    get_widget_settings,
    is_dashboard_admin,
    is_gadget_enabled,
)
from app.ui.page import DashboardPage
from app.ui.routes.admin_actions import (
    add_admin_route,
    admin_actions_router,
    extension_details_route,
    reload_extension_action,
    remove_admin_route,
    restart_api_action,
    restart_bot_action,
    restart_system_action,
    restart_ui_action,
    start_counters_route,
    stop_counters_route,
    toggle_api_key_route,
    toggle_gadget_route,
)

admin_router = APIRouter()
admin_router.routes.extend(admin_actions_router.routes)


def require_admin(f):
    """Defense-in-depth decorator verifying dashboard admin session for /admin/* routes."""
    original_sig = inspect.signature(f)

    @functools.wraps(f)
    async def wrapper(*args, **kwargs):
        sess = kwargs.get("sess")
        if sess is None:
            if "sess" in original_sig.parameters:
                idx = list(original_sig.parameters.keys()).index("sess")
                if idx < len(args):
                    sess = args[idx]
            elif len(args) > len(original_sig.parameters):
                sess = args[-1]
        if not sess:
            for arg in args:
                if hasattr(arg, "session"):
                    sess = getattr(arg, "session", {})
                    break

        auth = (sess or {}).get("auth", {}) if isinstance(sess, dict) else {}
        user_id = auth.get("id")
        is_admin = False
        if user_id is not None:
            try:
                is_admin = is_dashboard_admin(int(user_id))
            except (ValueError, TypeError):
                pass
        if not is_admin:
            return P("Forbidden", cls="text-error")

        f_args = args[: len(original_sig.parameters)] if "sess" not in original_sig.parameters else args
        f_kwargs = (
            {k: v for k, v in kwargs.items() if k in original_sig.parameters}
            if "sess" not in original_sig.parameters
            else kwargs
        )
        return await f(*f_args, **f_kwargs)

    if "sess" not in original_sig.parameters:
        params = list(original_sig.parameters.values())
        params.append(inspect.Parameter("sess", inspect.Parameter.POSITIONAL_OR_KEYWORD))
        wrapper.__signature__ = original_sig.replace(parameters=params)
    else:
        wrapper.__signature__ = original_sig
    return wrapper


def extension_card(
    extension_name: str,
    gadgets: list[str],
    enabled_cogs: list[str],
    enabled_sprockets: list[str],
    enabled_widgets: list[str],
) -> FT:
    """Renders a card for a single extension with toggles for its components."""
    reload_btn = Form(
        Hidden(name="extension_name", value=extension_name),
        Button(I(cls="fa-solid fa-rotate-right"), cls="btn btn-ghost btn-xs text-warning"),
        hx_post="/admin/extensions/reload",
        hx_target=f"#status-{extension_name}",
        hx_swap="innerHTML",
    )

    details_link = A(
        extension_name.capitalize(),
        cls="flex-grow font-bold text-lg cursor-pointer hover:underline text-base-content",
        hx_get=f"/admin/extensions/{extension_name}/details",
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
                id=f"all-{extension_name}-global",
                cls="toggle toggle-primary toggle-sm",
                hx_post="/admin/extensions/toggle",
                hx_trigger="change",
                hx_target=f"#extension-{extension_name}",
                hx_swap="outerHTML",
                hx_include="closest form",
            ),
            cls="label cursor-pointer p-0",
        ),
        Hidden(name="extension_name", value=extension_name),
        Hidden(name="gadget_type", value="all"),
        cls="flex items-center",
        id=f"form-all-{extension_name}-global",
    )

    status_div = Div(id=f"status-{extension_name}", cls="text-xs mr-2 ml-auto")
    title_comp = Div(details_link, toggle_form, status_div, reload_btn, cls="flex items-center w-full gap-2")

    return Card(
        title_comp,
        "",
        id=f"extension-{extension_name}",
    )


from app.ui.routes.admin_components import (
    _render_admin_api_keys,
    _render_admin_list,
)


@admin_router("/admin")
async def admin_home(sess):
    """The restricted admin dashboard."""
    auth = sess.get("auth", {})

    stats = {}
    try:
        async with get_internal_api_client() as client:
            resp = await client.get("http://127.0.0.1:8001/stats", timeout=2.0)
            if resp.status_code == 200:
                stats = resp.json()
            else:
                logging.error(f"Failed to fetch bot stats: Status {resp.status_code}")
    except Exception as e:
        logging.error(f"Failed to fetch bot stats: {e}", exc_info=True)

    sys_stats = stats.get("system", {})
    bot_stats = stats.get("bot", {})

    stats_grid = Div(
        Card(
            "System Stats",
            Div(
                Div(
                    Div(I(cls="fa-solid fa-microchip mr-2"), "CPU", cls="stat-title"),
                    Div(f"{sys_stats.get('cpu_percent', 'N/A')}%", cls="stat-value text-primary"),
                    Div("System Load", cls="stat-desc"),
                    cls="stat",
                ),
                Div(
                    Div(I(cls="fa-solid fa-memory mr-2"), "RAM", cls="stat-title"),
                    Div(f"{sys_stats.get('memory_percent', 'N/A')}%", cls="stat-value text-secondary"),
                    Div(
                        f"{sys_stats.get('memory_used_gb', 'N/A')}GB / {sys_stats.get('memory_total_gb', 'N/A')}GB",
                        cls="stat-desc",
                    ),
                    cls="stat",
                ),
                cls="stats stats-vertical lg:stats-horizontal w-full bg-transparent",
            ),
        ),
        Card(
            "Bot Stats",
            Div(
                Div(
                    Div(I(cls="fa-solid fa-server mr-2"), "Guilds", cls="stat-title"),
                    Div(f"{bot_stats.get('guilds', 'N/A')}", cls="stat-value text-primary"),
                    Div(f"{bot_stats.get('users', 'N/A')} users", cls="stat-desc"),
                    cls="stat",
                ),
                Div(
                    Div(I(cls="fa-solid fa-network-wired mr-2"), "Latency", cls="stat-title"),
                    Div(f"{bot_stats.get('latency', 'N/A')}ms", cls="stat-value text-secondary"),
                    Div("Ping", cls="stat-desc"),
                    cls="stat",
                ),
                cls="stats stats-vertical lg:stats-horizontal w-full bg-transparent",
            ),
        ),
        cls="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8",
    )

    logs = []
    try:
        async with get_internal_api_client() as client:
            resp = await client.get("http://127.0.0.1:8001/logs?limit=20", timeout=2.0)
            if resp.status_code == 200:
                logs = resp.json().get("logs", [])
            else:
                logging.error(f"Failed to fetch bot logs: Status {resp.status_code}")
    except Exception as e:
        logging.error(f"Failed to fetch bot logs: {e}", exc_info=True)

    logs_content = "\n".join([line.strip() for line in logs])
    terminal_header = Div(
        Div(cls="w-3 h-3 rounded-full bg-error"),
        Div(cls="w-3 h-3 rounded-full bg-warning"),
        Div(cls="w-3 h-3 rounded-full bg-success"),
        cls="flex gap-2 p-3 bg-[#1a1a1a] rounded-t-lg border-b border-[#333333]",
    )

    terminal_body = Div(
        Pre(
            Code(logs_content, cls="language-log font-mono text-[#00ff00]"),
            style="white-space: pre; word-break: normal; overflow-x: auto;",
        ),
        cls="p-4 max-h-[400px] overflow-y-auto overflow-x-hidden bg-black rounded-b-lg font-mono text-sm w-full",
    )

    logs_component = Div(
        Div("System Terminal", cls="text-lg font-bold mb-2 ml-1 opacity-70"),
        Div(
            terminal_header,
            terminal_body,
            cls="border border-[#444444] rounded-lg shadow-xl w-full overflow-hidden",
        ),
        cls="mb-8 w-full",
    )

    manage_admins_list = await _render_admin_list(sess)

    manage_admins = Div(
        H2("Manage Admins", cls="text-2xl font-bold mb-4"),
        Div(
            Div(
                H3("Add New Admin", cls="font-bold mb-2"),
                Form(
                    Input(
                        type="text",
                        name="user_id",
                        placeholder="Discord User ID",
                        cls="input input-bordered input-sm w-full max-w-xs mr-2",
                    ),
                    Input(
                        type="text",
                        name="comment",
                        placeholder="Comment (Optional)",
                        cls="input input-bordered input-sm w-full max-w-xs mr-2",
                    ),
                    Button("Add", cls="btn btn-primary btn-sm"),
                    hx_post="/admin/manage/add",
                    hx_target="#admin-list",
                    hx_swap="outerHTML",
                ),
                cls="mb-4",
            ),
            manage_admins_list,
            cls="card bg-base-100 shadow-sm border border-base-content/20 p-4",
        ),
        cls="mb-8",
    )

    inspector = GadgetInspector()
    all_extensions = inspector.inspect_extensions()

    if "powerloader" in all_extensions:
        del all_extensions["powerloader"]

    enabled_cogs = get_guild_cogs(0)
    enabled_sprockets = get_guild_sprockets(0)
    enabled_widgets = get_guild_widgets(0)

    extension_section = Div(
        H2("Manage Extensions (Global)", cls="text-2xl font-bold mb-4"),
        P(
            "Toggle extension components globally. Extensions disabled here will not be available in any server.",
            cls="mb-4 opacity-80",
        ),
        Div(
            *[
                extension_card(name, gadgets, enabled_cogs, enabled_sprockets, enabled_widgets)
                for name, gadgets in all_extensions.items()
            ],
            cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8",
        ),
        cls="mb-8",
    )

    all_widgets = inspector.inspect_widgets()
    settings = get_widget_settings(SCOPE_ADMIN_DASHBOARD)
    admin_widget_configs = []

    for ext_name, widget_funcs in all_widgets.items():
        if not is_gadget_enabled(0, ext_name, "widget"):
            continue

        for func in widget_funcs:
            w_name = get_widget_name(func)
            if not w_name or not w_name.startswith("admin_"):
                continue

            widget_setting = settings.get(w_name, {})
            if widget_setting.get("is_enabled", False):
                try:
                    sig = inspect.signature(func)
                    kwargs = {}
                    if "access_token" in sig.parameters:
                        kwargs["access_token"] = auth.get("token_data", {}).get("access_token")

                    admin_widget_configs.append(
                        {
                            "component": func(**kwargs),
                            "order": widget_setting.get("display_order", 99),
                            "span": widget_setting.get("column_span", 4),
                        }
                    )
                except Exception as e:
                    logging.error(f"Failed to render admin widget {w_name}: {e}")

    admin_widget_configs.sort(key=lambda x: x["order"])
    rendered_admin_widgets = [
        Div(c["component"], style=f"grid-column: span {c['span']};") for c in admin_widget_configs
    ]

    restart_section = Div(
        H2("System Management", cls="text-2xl font-bold mb-4"),
        Div(
            P(
                "Restart system components. In production (or when using 'just run'), the process manager will automatically restart them.  When running locally with 'just dev', these buttons will only STOP the components.",
                cls="mb-4 opacity-80",
            ),
            Div(
                Form(
                    Button(
                        I(cls="fa-solid fa-robot mr-2"),
                        "Restart Bot (Cogs)",
                        cls="btn btn-error btn-sm w-full h-auto py-2",
                        onclick="return confirm('Restart the Bot?');",
                    ),
                    Div(id="bot-status", cls="text-xs text-center mt-2"),
                    hx_post="/admin/bot/restart",
                    hx_target="#bot-status",
                    hx_swap="innerHTML",
                ),
                Form(
                    Button(
                        I(cls="fa-solid fa-server mr-2"),
                        "Restart API (Sprockets)",
                        cls="btn btn-warning btn-sm w-full h-auto py-2",
                        onclick="return confirm('Restart the API?');",
                    ),
                    Div(id="api-status", cls="text-xs text-center mt-2"),
                    hx_post="/admin/api/restart",
                    hx_target="#api-status",
                    hx_swap="innerHTML",
                ),
                Form(
                    Button(
                        I(cls="fa-solid fa-desktop mr-2"),
                        "Restart UI (Widgets)",
                        cls="btn btn-info btn-sm w-full h-auto py-2",
                        onclick="return confirm('Restart the UI?');",
                    ),
                    Div(id="ui-status", cls="text-xs text-center mt-2"),
                    hx_post="/admin/ui/restart",
                    hx_target="#ui-status",
                    hx_swap="innerHTML",
                ),
                Form(
                    Button(
                        I(cls="fa-solid fa-power-off mr-2"),
                        "Restart All",
                        cls="btn btn-error btn-sm w-full h-auto py-2 outline outline-2 outline-error-content",
                        onclick="return confirm('Restart ALL system components?');",
                    ),
                    Div(id="system-status", cls="text-xs text-center mt-2"),
                    hx_post="/admin/system/restart",
                    hx_target="#system-status",
                    hx_swap="innerHTML",
                ),
                cls="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4",
            ),
            cls="card bg-base-100 shadow-sm border border-base-content/20 p-4",
        ),
        cls="mb-8",
    )

    admin_widgets = Div(
        Div(
            H2("Admin Widgets", cls="text-2xl font-bold"),
            A(
                I(cls="fa-solid fa-pen-to-square mr-1"),
                "Edit Layout",
                href="/admin/layout/admin",
                cls="btn btn-sm btn-ghost text-info",
            ),
            cls="flex justify-between items-center mb-4",
        ),
        Div(*rendered_admin_widgets, cls="grid grid-cols-12 gap-6")
        if rendered_admin_widgets
        else P("No admin widgets enabled. Click 'Edit Layout' to configure."),
        cls="mb-8",
    )

    manage_api_keys = await _render_admin_api_keys(sess)

    return DashboardPage(
        "Admin Dashboard",
        H1("System Administration", cls="text-2xl font-extrabold mb-8"),
        stats_grid,
        logs_component,
        manage_admins,
        manage_api_keys,
        extension_section,
        restart_section,
        admin_widgets,
        auth=auth,
    )


__all__ = [
    "admin_router",
    "admin_home",
    "extension_card",
    "require_admin",
    "_render_admin_list",
    "_render_admin_api_keys",
    "start_counters_route",
    "stop_counters_route",
    "add_admin_route",
    "remove_admin_route",
    "toggle_api_key_route",
    "reload_extension_action",
    "toggle_gadget_route",
    "restart_bot_action",
    "restart_api_action",
    "restart_ui_action",
    "restart_system_action",
    "extension_details_route",
]
