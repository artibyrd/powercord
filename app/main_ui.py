# mypy: ignore-errors
# TODO: Enable mypy strict checking for this file (currently excluded in pyproject.toml)
import functools
import inspect
import json
import logging
import os
import signal
from pathlib import Path

import httpx

try:
    # When running as a script (e.g. python app/main_ui.py)
    import bootstrap
except ImportError:
    # When importing as a module (e.g. pytest)
    from app import bootstrap
bootstrap.setup_project_root()

import app

app.setup_logging("powercord")


from fasthtml.common import *

import app.common.gsm_loader as gsecrets
from app.common.extension_loader import GadgetInspector
from app.ui.auth import auth_before, auth_router
from app.ui.components import Accordion, Card
from app.ui.dashboard import dashboard_router
from app.ui.helpers import (
    SCOPE_ADMIN_DASHBOARD,
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
)
from app.ui.page import DashboardPage

gsecrets.load_env()


def require_admin(f):
    """Defense-in-depth decorator for /admin/* route handlers.

    Verifies the session user is a dashboard admin before executing
    the wrapped handler.  Complements the Beforeware check so that
    a regression in auth_before cannot silently expose admin operations.

    NOTE: The wrapper must preserve ``__signature__`` because FastHTML
    inspects handler signatures for automatic parameter injection
    (``req``, ``sess``, path params, etc.).
    """

    @functools.wraps(f)
    async def wrapper(*args, **kwargs):
        # FastHTML injects `sess` by name; grab it from kwargs.
        sess = kwargs.get("sess")
        if sess is None:
            # If not in kwargs, it might be passed positionally. Find the position of 'sess' in f's signature.
            sig = inspect.signature(f)
            for idx, param_name in enumerate(sig.parameters):
                if param_name == "sess" and idx < len(args):
                    sess = args[idx]
                    break
        if sess is None:
            sess = {}

        from app.ui.helpers import is_dashboard_admin

        auth = sess.get("auth", {}) if isinstance(sess, dict) else {}
        user_id = auth.get("id")
        is_admin = False
        if user_id:
            try:
                is_admin = is_dashboard_admin(int(user_id))
            except (ValueError, TypeError):
                pass
        if not is_admin:
            return P("Forbidden", cls="text-error")
        return await f(*args, **kwargs)

    # Preserve the original signature so FastHTML's parameter
    # injector can still resolve `req`, `sess`, path params, etc.
    original_sig = inspect.signature(f)
    # Ensure `sess` is in the signature (some handlers didn't have it)
    if "sess" not in original_sig.parameters:
        params = list(original_sig.parameters.values())
        params.append(inspect.Parameter("sess", inspect.Parameter.POSITIONAL_OR_KEYWORD))
        wrapper.__signature__ = original_sig.replace(parameters=params)
    else:
        wrapper.__signature__ = original_sig
    return wrapper


# Define a Beforeware to apply authentication to all necessary routes.
# We will skip the public-facing and authentication-related routes.
beforeware = Beforeware(
    auth_before,
    skip=[
        "/",
        "/login",
        "/logout",
        "/auth/discord/callback",
        "/dev/login",  # Dev convenience route must bypass auth
        r"/static/.*",
        r"/favicon\.ico",
    ],
)

# Dynamically collect public-facing paths declared by installed extensions.
# Each extension can define a PUBLIC_PATHS list[str] in its routes.py module
# to register auth-bypass patterns without modifying this file.
_route_inspector = GadgetInspector()
beforeware.skip.extend(_route_inspector.collect_public_paths())

# Setup app with session middleware and include auth routes.
hdrs = (
    Link(rel="icon", href="/static/favicon.png", type="image/png"),
    # DaisyUI component CSS must load BEFORE the Tailwind CDN play script.
    # The play script's JIT compiler will then layer utility classes on top
    # without clobbering DaisyUI's component rules (e.g. .toggle, .checkbox).
    Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css"),
    Script(src="https://cdn.tailwindcss.com"),
    # Tell the Tailwind play CDN that DaisyUI is a plugin so it does not
    # purge/override component classes it doesn't recognise.
    Script("""tailwind.config = { daisyui: { themes: ["synthwave"] } }"""),
    Link(rel="stylesheet", href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css"),
    Link(
        rel="stylesheet",
        href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400..900&family=Share+Tech+Mono&display=swap",
    ),
    Link(rel="stylesheet", href="/static/theme.css?v=synthwave_v4"),
    # Use marked.js for markdown rendering
    Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
    # html-midi-player: web component for in-browser MIDI playback
    Script(
        src="https://cdn.jsdelivr.net/combine/npm/tone@14.7.77,npm/@magenta/music@1.23.1/es6/core.js,npm/html-midi-player@1.5.0"
    ),
)

from starlette.staticfiles import StaticFiles

app, rt = fast_app(
    secret_key=os.getenv("POWERCORD_SESSION_KEY"),
    before=beforeware,
    hdrs=hdrs,
    htmlkw={"data-theme": "synthwave"},
    pico=False,
)
static_dir = Path(__file__).parent / "static"
from starlette.routing import Mount

dashboard_router.to_app(app)


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


app.routes.insert(0, Mount("/static", StaticFiles(directory=static_dir), name="static"))  # type: ignore[attr-defined]
setup_toasts(app)
auth_router.to_app(app)
dashboard_router.to_app(app)


@rt("/")
def public_home(sess: dict):
    """The main public-facing page, composed of widgets."""
    inspector = GadgetInspector()
    all_widgets_by_ext = inspector.inspect_widgets()

    auth = sess.get("auth")

    # For the public page, we use the global layout settings (guild_id=0)
    settings = get_widget_settings(0)

    # Flatten all widget functions and pair with their settings.
    widget_configs = []
    for ext_name, widget_funcs in all_widgets_by_ext.items():
        # Check if widget component is globally enabled for this extension
        if not is_gadget_enabled(0, ext_name, "widget"):
            continue

        for func in widget_funcs:
            widget_name = get_widget_name(func)
            if not widget_name:
                continue

            # Skip admin and guild admin widgets on public page
            if widget_name.startswith("admin_") or widget_name.startswith("guild_admin_"):
                continue

            widget_setting = settings.get(widget_name, {})
            if widget_setting.get("is_enabled", False):
                widget_configs.append(
                    {
                        "component": func(),
                        "order": widget_setting.get("display_order", 99),
                        "span": widget_setting.get("column_span", 4),
                    }
                )

    # Sort widgets by display order and apply column span styles
    widget_configs.sort(key=lambda x: x["order"])
    styled_components = [Div(c["component"], style=f"grid-column: span {c['span']};") for c in widget_configs]

    content = [
        Div(*styled_components, cls="grid grid-cols-12 gap-4")
        if styled_components
        else P("No widgets are currently enabled."),
    ]

    return DashboardPage(
        "Welcome",
        *content,
        auth=auth,
    )


async def _render_client_keys(sess):
    from sqlmodel import Session, select

    from app.common.alchemy import init_connection_engine
    from app.db.models import ApiKey
    from app.ui.helpers import is_dashboard_admin

    auth = sess.get("auth", {})
    user_id = auth.get("id")
    if not user_id:
        return Div()

    is_admin = False
    try:
        is_admin = is_dashboard_admin(int(user_id))
    except (ValueError, TypeError):
        pass

    if not is_admin:
        return Div(
            H2("Companion Client Keys", cls="text-2xl font-bold mb-4"),
            P(
                "Companion Client key generation and management is restricted to global administrators.",
                cls="text-error mb-4",
            ),
            id="client-keys-container",
            cls="mb-8",
        )

    prefix = f"client_{user_id}_"
    engine = init_connection_engine()

    with Session(engine) as session:
        stmt = select(ApiKey).where(ApiKey.name.startswith(prefix)).where(ApiKey.is_active)
        active_keys = session.exec(stmt).all()

    key_rows = []
    for k in active_keys:
        key_rows.append(
            Tr(
                Td(str(k.id)),
                Td(k.name, cls="font-mono text-xs opacity-70"),
                Td(Code("••••••••••••••••", cls="bg-base-300 p-1 rounded"), cls="font-mono text-sm text-success"),
                Td(
                    Form(
                        Hidden(name="key_id", value=str(k.id)),
                        Button("Revoke", cls="btn btn-error btn-xs"),
                        hx_post="/profile/client-key/revoke",
                        hx_target="#client-keys-container",
                        hx_swap="outerHTML",
                    )
                ),
            )
        )

    table = (
        Table(
            Thead(Tr(Th("ID"), Th("Name"), Th("API Key"), Th("Action"))),
            Tbody(*key_rows),
            cls="table w-full",
        )
        if key_rows
        else P("You have no active client keys.", cls="italic opacity-70 mb-4")
    )

    from app.common.extension_loader import GadgetInspector

    inspector = GadgetInspector()
    ext_names = list(inspector.inspect_extensions().keys())
    if "powerloader" in ext_names:
        ext_names.remove("powerloader")

    scope_options = [
        ("Global: admin", "global.admin"),
        ("Global: user", "global.user"),
    ]
    for ext in ext_names:
        scope_options.append((f"Global: {ext}.admin", f"global.{ext}.admin"))
        scope_options.append((f"Global: {ext}.user", f"global.{ext}.user"))

    scope_checkboxes = []
    for label, val in scope_options:
        scope_checkboxes.append(
            Label(
                Input(
                    type="checkbox",
                    name="scope",
                    value=val,
                    cls="checkbox checkbox-primary checkbox-sm",
                ),
                Span(label, cls="ml-3 text-sm font-medium text-base-content/85"),
                cls="flex items-center p-3 bg-base-300/40 border border-base-content/20 rounded-lg cursor-pointer hover:bg-base-300/80 transition-all duration-200 w-full max-w-sm",
            )
        )

    tooltip = Div(
        I(cls="fa-solid fa-circle-info cursor-help text-info"),
        cls="tooltip tooltip-right ml-2",
        data_tip='Available global scopes include "global.admin", "global.user", "global.{extension}.admin", etc.',
    )

    show_form_btn = Button(
        I(cls="fa-solid fa-plus mr-2"),
        "Generate Client Key",
        cls="btn btn-primary btn-sm mt-2",
        onclick="document.getElementById('client-key-gen-form').classList.remove('hidden'); this.classList.add('hidden');",
        id="show-client-keygen-btn",
    )

    generate_form = Form(
        Div(
            Div(
                Label("Select Scope(s):", cls="label-text mb-1 font-semibold text-xs opacity-70"),
                tooltip,
                cls="flex items-center mb-1",
            ),
            Div(*scope_checkboxes, cls="grid grid-cols-1 md:grid-cols-2 gap-2 mb-4 max-w-2xl"),
            cls="flex flex-col gap-1",
        ),
        Div(
            Button(I(cls="fa-solid fa-key mr-2"), "Generate Key", cls="btn btn-primary btn-sm"),
            Button(
                "Cancel",
                type="button",
                cls="btn btn-ghost btn-sm",
                onclick="document.getElementById('client-key-gen-form').classList.add('hidden'); document.getElementById('show-client-keygen-btn').classList.remove('hidden');",
            ),
            cls="flex items-center gap-2 mt-4",
        ),
        hx_post="/profile/client-key/generate",
        hx_target="#client-keys-container",
        hx_swap="outerHTML",
        cls="mt-4 hidden p-4 bg-base-300/30 rounded-lg",
        id="client-key-gen-form",
    )

    return Div(
        H2("Companion Client Keys", cls="text-2xl font-bold mb-4"),
        P(
            "Use these keys to authenticate the Powercord Desktop or Mobile application. Do not share them.",
            cls="mb-4 opacity-80",
        ),
        Div(
            table,
            show_form_btn,
            generate_form,
            cls="card bg-base-100 shadow-sm border border-base-content/20 p-4",
        ),
        id="client-keys-container",
        cls="mb-8",
    )


@rt("/profile/client-key/generate", methods=["POST"])
async def generate_client_key_route(req, sess):
    import hashlib
    import json
    import secrets

    from sqlmodel import Session

    from app.common.alchemy import init_connection_engine
    from app.db.models import ApiKey
    from app.ui.helpers import is_dashboard_admin

    auth = sess.get("auth", {})
    user_id = auth.get("id")
    if user_id:
        try:
            is_admin = is_dashboard_admin(int(user_id))
        except (ValueError, TypeError):
            is_admin = False

        if not is_admin:
            return await _render_client_keys(sess)

        form = await req.form()
        if hasattr(form, "getlist"):
            selected_scopes = form.getlist("scope")
        else:
            selected_scopes = form.get("scope")
            if isinstance(selected_scopes, str):
                selected_scopes = [selected_scopes]
            elif not selected_scopes:
                selected_scopes = []
        if not selected_scopes:
            selected_scopes = ["global.admin"]
        scopes = json.dumps(selected_scopes)
        random_suffix = secrets.token_hex(4)
        name = f"client_{user_id}_{random_suffix}"
        new_key = f"pc_{secrets.token_urlsafe(32)}"
        new_key_hash = hashlib.sha256(new_key.encode("utf-8")).hexdigest()

        engine = init_connection_engine()
        with Session(engine) as session:
            api_key = ApiKey(
                key_hash=new_key_hash,
                name=name,
                scopes=scopes,
                is_active=True,
                key_type="global",
            )
            session.add(api_key)
            session.commit()

        add_toast(
            sess,
            f"New client key generated: {new_key} (Copy this now; it will not be displayed again!)",
            "success",
            dismiss=True,
        )

    return await _render_client_keys(sess)


@rt("/profile/client-key/revoke", methods=["POST"])
async def revoke_client_key_route(req, sess):
    from sqlmodel import Session

    from app.common.alchemy import init_connection_engine
    from app.db.models import ApiKey
    from app.ui.helpers import is_dashboard_admin

    auth = sess.get("auth", {})
    user_id = auth.get("id")
    if not user_id:
        return await _render_client_keys(sess)

    try:
        is_admin = is_dashboard_admin(int(user_id))
    except (ValueError, TypeError):
        is_admin = False

    if not is_admin:
        return await _render_client_keys(sess)

    form = await req.form()
    key_id_str = form.get("key_id")

    if key_id_str:
        try:
            key_id = int(key_id_str)
            engine = init_connection_engine()
            with Session(engine) as session:
                api_key = session.get(ApiKey, key_id)
                # Verify it belongs to the user
                if api_key and api_key.name.startswith(f"client_{user_id}_"):
                    api_key.is_active = False
                    session.add(api_key)
                    session.commit()
                    add_toast(sess, "Client key revoked successfully.", "success", dismiss=True)
        except ValueError:
            pass

    return await _render_client_keys(sess)


@rt("/profile")
async def profile_page(sess):
    """The user profile page, showing connected servers and session data."""
    auth = sess.get("auth", {})
    username = auth.get("username", "User")

    token_data = auth.get("token_data", {})
    user_access_token = token_data.get("access_token")

    admin_guilds = {}
    if user_access_token:
        try:
            user_id = int(auth.get("id"))
            admin_guilds = await get_admin_guilds(user_access_token, user_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                add_toast(sess, "Discord session expired. Please log in again.", "error")
                return RedirectResponse("/logout", status_code=303)
            logging.error(f"Failed to fetch guild information in route: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"Failed to fetch guild information in route: {e}", exc_info=True)

    def guild_card(guild):
        icon_url = (
            f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png"
            if guild["icon"]
            else "https://cdn.discordapp.com/embed/avatars/0.png"
        )
        return Div(
            Div(
                Div(
                    Img(src=icon_url, width=48, height=48, cls="rounded-full flex-shrink-0"),
                    Div(
                        H3(guild["name"], cls="font-bold text-lg line-clamp-2"),
                    ),
                    cls="flex items-center gap-3 flex-grow min-w-0",
                ),
                A(
                    "Configure",
                    href=f"/dashboard/{guild['id']}",
                    cls="btn btn-outline btn-primary btn-sm flex-shrink-0",
                ),
                cls="flex items-center justify-between gap-4 p-4",
            ),
            cls="card bg-base-300 shadow-sm border border-base-content/20 rounded-xl",
        )

    server_list = Div(
        H2("Your Servers", cls="text-2xl font-bold mb-4"),
        Div(
            *[guild_card(g) for g in admin_guilds.values()],
            cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4",
        )
        if admin_guilds
        else P("No shared admin servers found."),
        cls="mb-8",
    )

    # Session Data Section
    session_data = Div(
        Accordion(
            "Session Data",
            Div(
                Div(id="json-tree", cls="font-mono text-sm"),
                Script(f"""
                    (function() {{
                        const data = {json.dumps(auth)};
                        function renderJson(obj, depth) {{
                            if (obj === null) return '<span style="color:#f472b6">null</span>';
                            if (typeof obj === 'boolean') return '<span style="color:#f472b6">' + obj + '</span>';
                            if (typeof obj === 'number') return '<span style="color:#7dd3fc">' + obj + '</span>';
                            if (typeof obj === 'string') return '<span style="color:#86efac">"' + obj.replace(/</g,'&lt;') + '"</span>';
                            const isArray = Array.isArray(obj);
                            const entries = isArray ? obj.map((v,i) => [i,v]) : Object.entries(obj);
                            if (entries.length === 0) return isArray ? '[]' : '{{}}';
                            let html = '';
                            entries.forEach(([key, val]) => {{
                                const isExpandable = val !== null && typeof val === 'object';
                                if (isExpandable) {{
                                    const count = Array.isArray(val) ? val.length : Object.keys(val).length;
                                    const bracket = Array.isArray(val) ? '[' + count + ']' : '{{' + count + '}}';
                                    html += '<details style="margin-left:' + (depth*16) + 'px;padding:2px 0">' +
                                        '<summary style="cursor:pointer;list-style:disclosure-closed;color:#94a3b8">' +
                                        '<span style="color:#fbbf24">' + (isArray ? '' : '"' + key + '": ') + '</span>' +
                                        '<span style="color:#64748b;font-size:0.85em">' + bracket + '</span></summary>' +
                                        renderJson(val, depth+1) + '</details>';
                                }} else {{
                                    html += '<div style="margin-left:' + (depth*16) + 'px;padding:2px 0;color:#94a3b8">' +
                                        (isArray ? '' : '<span style="color:#fbbf24">"' + key + '"</span>: ') +
                                        renderJson(val, depth+1) + '</div>';
                                }}
                            }});
                            return html;
                        }}
                        document.getElementById('json-tree').innerHTML = renderJson(data, 0);
                    }})();
                """),
                cls="card-body",
            ),
            open=False,
        ),
        cls="mb-8",
    )

    client_keys_section = await _render_client_keys(sess)

    return DashboardPage(
        "Profile",
        H1(f"Welcome, {username}!", cls="text-2xl font-extrabold mb-8"),
        server_list,
        client_keys_section,
        session_data,
        auth=auth,
    )


@rt("/admin")
async def admin_home(sess):
    """The restricted admin dashboard."""
    auth = sess.get("auth", {})

    # Fetch stats from Bot API
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

    # Stats Components
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

    # Fetch logs from Bot API
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

    # --- Manage Admins Section ---
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

    # --- Manage Extensions Section (Global) ---
    inspector = GadgetInspector()
    all_extensions = inspector.inspect_extensions()

    # powerloader is a core bot component
    if "powerloader" in all_extensions:
        del all_extensions["powerloader"]

    # Fetch GLOBAL enabled state (guild_id=0)
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

    # Admin Widgets Section
    all_widgets = inspector.inspect_widgets()

    # Fetch Admin Dashboard Layout Settings
    settings = get_widget_settings(SCOPE_ADMIN_DASHBOARD)

    admin_widget_configs = []

    for ext_name, widget_funcs in all_widgets.items():
        # Check if widget component is globally enabled
        if not is_gadget_enabled(0, ext_name, "widget"):
            continue

        for func in widget_funcs:
            w_name = get_widget_name(func)

            # Admin Dashboard ONLY shows admin_ widgets
            if not w_name or not w_name.startswith("admin_"):
                continue

            widget_setting = settings.get(w_name, {})
            # Only show if enabled in Admin Dashboard Layout
            if widget_setting.get("is_enabled", False):
                try:
                    import inspect

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

    # Sort and style
    admin_widget_configs.sort(key=lambda x: x["order"])
    rendered_admin_widgets = [
        Div(c["component"], style=f"grid-column: span {c['span']};") for c in admin_widget_configs
    ]

    # --- System Management Section ---
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


@rt("/admin/examples/counters/start", methods=["POST"])
@require_admin
async def start_counters_route(req):
    """Starts the example counters via Bot API."""
    try:
        async with get_internal_api_client() as client:
            resp = await client.post("http://127.0.0.1:8001/examples/counters", json={"action": "start"}, timeout=5.0)
            if resp.status_code == 200:
                return P("Counters started successfully!", style="color: green;")
            else:
                return P(f"Failed to start counters: {resp.text}", style="color: red;")
    except Exception as e:
        return P(f"Error communicating with bot: {e}", style="color: red;")


@rt("/admin/examples/counters/stop", methods=["POST"])
@require_admin
async def stop_counters_route(req):
    """Stops the example counters via Bot API."""
    try:
        async with get_internal_api_client() as client:
            resp = await client.post("http://127.0.0.1:8001/examples/counters", json={"action": "stop"}, timeout=5.0)
            if resp.status_code == 200:
                return P("Counters stopped successfully!", style="color: green;")
            else:
                return P(f"Failed to stop counters: {resp.text}", style="color: red;")
    except Exception as e:
        return P(f"Error communicating with bot: {e}", style="color: red;")


@rt("/admin/manage/add", methods=["POST"])
@require_admin
async def add_admin_route(req, sess):
    form = await req.form()
    try:
        user_id = int(form.get("user_id"))
        comment = form.get("comment")
        from app.ui.helpers import add_dashboard_admin

        add_dashboard_admin(user_id, comment)
    except ValueError:
        pass  # Invalid ID format

    return await _render_admin_list(sess)


@rt("/admin/manage/remove", methods=["POST"])
@require_admin
async def remove_admin_route(req, sess):
    form = await req.form()
    try:
        user_id = int(form.get("user_id"))
        from app.ui.helpers import remove_dashboard_admin

        remove_dashboard_admin(user_id)
    except ValueError:
        pass

    return await _render_admin_list(sess)


async def _render_admin_list(sess):
    auth = sess.get("auth", {})
    from app.ui.helpers import get_dashboard_admins, get_discord_username

    admins = get_dashboard_admins()

    admin_rows = []
    for admin in admins:
        # Fetch username from Discord API
        username = await get_discord_username(admin.user_id)

        admin_rows.append(
            Tr(
                Td(str(admin.user_id)),
                Td(username, cls="font-semibold text-primary"),
                Td(admin.comment or ""),
                Td(
                    Form(
                        Hidden(name="user_id", value=str(admin.user_id)),
                        Button("Remove", cls="btn btn-error btn-xs"),
                        hx_post="/admin/manage/remove",
                        hx_target="#admin-list",
                        hx_swap="outerHTML",
                        method="post",
                        style="display:inline;",
                    )
                    if admin.user_id != int(auth.get("id"))
                    else Span("You", cls="badge badge-ghost")
                ),
            )
        )

    return Div(
        Table(
            Thead(Tr(Th("User ID"), Th("Username"), Th("Comment"), Th("Actions"))),
            Tbody(*admin_rows),
            cls="table w-full",
            id="admin-list-body",
        ),
        id="admin-list",
    )


async def _render_admin_api_keys(sess):
    from sqlmodel import Session, select

    from app.common.alchemy import init_connection_engine
    from app.db.models import ApiKey

    engine = init_connection_engine()
    with Session(engine) as session:
        stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
        keys = session.exec(stmt).all()

    key_rows = []
    for k in keys:
        import json

        try:
            scopes_list = json.loads(k.scopes)
        except Exception:
            scopes_list = []
        scopes_str = ", ".join(scopes_list)

        status_badge = (
            Span("Active", cls="badge badge-success badge-sm")
            if k.is_active
            else Span("Inactive", cls="badge badge-ghost badge-sm")
        )

        action_btn = Form(
            Hidden(name="key_id", value=str(k.id)),
            Hidden(name="action", value="revoke" if k.is_active else "reactivate"),
            Button(
                "Revoke" if k.is_active else "Reactivate",
                cls=f"btn {'btn-warning' if k.is_active else 'btn-success'} btn-xs",
            ),
            hx_post="/admin/api-key/toggle",
            hx_target="#admin-api-keys-list",
            hx_swap="outerHTML",
            style="display:inline-block;",
        )

        key_rows.append(
            Tr(
                Td(str(k.id)),
                Td(k.name, cls="font-mono text-xs opacity-70"),
                Td(status_badge),
                Td(k.key_type, cls="text-xs"),
                Td(scopes_str, cls="font-mono text-xs max-w-xs truncate"),
                Td(k.created_at.strftime("%Y-%m-%d %H:%M:%S") if k.created_at else "N/A"),
                Td(action_btn),
            )
        )

    table = (
        Table(
            Thead(
                Tr(
                    Th("ID"),
                    Th("Name"),
                    Th("Status"),
                    Th("Type"),
                    Th("Scopes"),
                    Th("Created At"),
                    Th("Actions"),
                )
            ),
            Tbody(*key_rows),
            cls="table w-full",
        )
        if key_rows
        else P("No API keys found in database.", cls="italic opacity-70")
    )

    return Div(
        H2("Manage API Keys", cls="text-2xl font-bold mb-4"),
        Div(
            table,
            cls="card bg-base-100 shadow-sm border border-base-content/20 p-4 max-h-96 overflow-y-auto",
        ),
        id="admin-api-keys-list",
        cls="mb-8",
    )


@rt("/admin/api-key/toggle", methods=["POST"])
@require_admin
async def toggle_api_key_route(req, sess):
    from sqlmodel import Session

    from app.common.alchemy import init_connection_engine
    from app.db.models import ApiKey
    from app.ui.helpers import is_dashboard_admin

    auth = sess.get("auth", {})
    user_id = auth.get("id")
    if not user_id:
        return P("Unauthorized", cls="text-error")

    try:
        is_admin = is_dashboard_admin(int(user_id))
    except (ValueError, TypeError):
        is_admin = False

    if not is_admin:
        return P("Forbidden", cls="text-error")

    form = await req.form()
    key_id_str = form.get("key_id")
    action = form.get("action")

    if key_id_str and action in ("revoke", "reactivate"):
        try:
            key_id = int(key_id_str)
            engine = init_connection_engine()
            with Session(engine) as session:
                api_key = session.get(ApiKey, key_id)
                if api_key:
                    api_key.is_active = action == "reactivate"
                    session.add(api_key)
                    session.commit()
                    add_toast(
                        sess,
                        f"API Key '{api_key.name}' {'reactivated' if action == 'reactivate' else 'revoked'} successfully.",
                        "success",
                        dismiss=True,
                    )
        except ValueError:
            pass

    return await _render_admin_api_keys(sess)


@rt("/admin/extensions/reload", methods=["POST"])
@require_admin
async def reload_extension_action(req):
    """Handles reloading a specific extension (Global)."""
    form_data = await req.form()
    extension_name = form_data.get("extension_name")

    try:
        async with get_internal_api_client() as client:
            resp = await client.post(f"http://127.0.0.1:8001/extensions/{extension_name}/reload", timeout=5.0)
            if resp.status_code == 200:
                return P(f"Extension '{extension_name}' reloaded successfully!", style="color: green;")
            else:
                return P(f"Failed to reload '{extension_name}': {resp.text}", style="color: red;")
    except Exception as e:
        return P(f"Error communicating with bot: {e}", style="color: red;")


@rt("/admin/extensions/toggle", methods=["POST"])
@require_admin
async def toggle_gadget_route(req):
    """Handles toggling an extension on/off globally (guild_id=0)."""
    form_data = await req.form()
    print("Toggle payload:", form_data)
    extension_name = form_data.get("extension_name")
    is_enabled = form_data.get("enabled") == "on"
    guild_id = 0  # Global setting

    logging.info(f"Toggle global: Ext={extension_name} Enabled={is_enabled}")

    inspector = GadgetInspector()
    all_extensions = inspector.inspect_extensions()
    gadgets = all_extensions.get(extension_name, [])

    # Update database for all components the extension realistically possesses
    for g_type in gadgets:
        update_guild_extension_setting(guild_id, extension_name, g_type, is_enabled)

    # Auto-reload/unload cog in the running bot
    status_msg = ""
    if "cog" in gadgets:
        try:
            async with get_internal_api_client() as client:
                # Check if the cog has preload requirements (persistent views/modals)
                check_resp = await client.get(
                    f"http://127.0.0.1:8001/extensions/{extension_name}/hotload-check", timeout=3.0
                )
                requires_restart = False
                if check_resp.status_code == 200:
                    requires_restart = check_resp.json().get("requires_restart", False)

                if requires_restart:
                    status_msg = "⚠️ Restart required for this cog."
                elif is_enabled:
                    # Load/reload the cog in the running bot
                    resp = await client.post(f"http://127.0.0.1:8001/extensions/{extension_name}/reload", timeout=5.0)
                    if resp.status_code == 200:
                        status_msg = "✅ Loaded"
                    else:
                        status_msg = f"⚠️ Load failed: {resp.text}"
                else:
                    # Unload the cog from the running bot
                    resp = await client.post(f"http://127.0.0.1:8001/extensions/{extension_name}/unload", timeout=5.0)
                    if resp.status_code == 200:
                        status_msg = "✅ Unloaded"
                    else:
                        status_msg = f"⚠️ Unload failed: {resp.text}"
        except Exception as e:
            logging.error(f"Auto-reload/unload failed for cog '{extension_name}': {e}")
            status_msg = "⚠️ Bot unreachable"

    if "sprocket" in gadgets:
        await notify_api_of_config_change(guild_id)

    # Recreate the updated extension card directly
    enabled_cogs = get_guild_cogs(0)
    enabled_sprockets = get_guild_sprockets(0)
    enabled_widgets = get_guild_widgets(0)

    card = extension_card(extension_name, gadgets, enabled_cogs, enabled_sprockets, enabled_widgets)

    if status_msg:
        # Provide out-of-band updates for the status since it's nested inside the card
        return card, Div(status_msg, id=f"status-{extension_name}", cls="text-xs mr-2", hx_swap_oob="true")

    return card


@rt("/admin/bot/restart", methods=["POST"])
@require_admin
async def restart_bot_action(req):
    """Sends a restart request to the bot's internal API."""
    try:
        async with get_internal_api_client() as client:
            resp = await client.post("http://127.0.0.1:8001/bot/restart", timeout=5.0)
            if resp.status_code == 200:
                return P("Bot restart initiated.", style="color: green;")
            else:
                return P(f"Failed to restart bot: {resp.text}", style="color: red;")
    except httpx.ReadError:
        return P("Bot restart initiated.", style="color: green;")
    except Exception as e:
        return P(f"Error communicating with bot: {e}", style="color: red;")


@rt("/admin/api/restart", methods=["POST"])
@require_admin
async def restart_api_action(req):
    """Sends a restart request to the backend API."""
    try:
        async with get_internal_api_client() as client:
            resp = await client.post("http://127.0.0.1:8000/restart", timeout=5.0)
            if resp.status_code == 200:
                return P("API restart initiated.", style="color: green;")
            else:
                return P(f"Failed to restart API: {resp.text}", style="color: red;")
    except httpx.ReadError:
        return P("API restart initiated.", style="color: green;")
    except Exception as e:
        return P(f"Error communicating with API: {e}", style="color: red;")


@rt("/admin/ui/restart", methods=["POST"])
@require_admin
async def restart_ui_action(req):
    """Restarts the UI process gracefully."""
    logging.info("UI: Received restart request. Exiting...")
    import asyncio

    async def _kill():
        await asyncio.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_kill())
    return P("UI restart initiated.", style="color: green;")


@rt("/admin/system/restart", methods=["POST"])
@require_admin
async def restart_system_action(req):
    """Restarts Bot, API, and UI."""
    msgs = []

    # 1. Restart Bot
    try:
        async with get_internal_api_client() as client:
            await client.post("http://127.0.0.1:8001/bot/restart", timeout=2.0)
        msgs.append("Bot restarted.")
    except Exception:
        msgs.append("Bot restart initiated.")

    # 2. Restart API
    try:
        async with get_internal_api_client() as client:
            await client.post("http://127.0.0.1:8000/restart", timeout=2.0)
        msgs.append("API restarted.")
    except Exception:
        msgs.append("API restart initiated.")

    # 3. Restart UI
    import asyncio

    async def _kill():
        await asyncio.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_kill())
    msgs.append("UI restart initiated.")

    return P("All system restarts initiated.", style="color: green;")


@rt("/admin/extensions/{extension_name}/details", methods=["GET"])
@require_admin
async def extension_details_route(extension_name: str, req):
    """Returns a modal with the extension details (Global admin)."""
    from app.ui.helpers import get_extension_details_modal

    auth_data = req.session.get("auth", {})
    token_data = auth_data.get("token_data", {})
    access_token = token_data.get("access_token")
    return get_extension_details_modal(extension_name, access_token=access_token)


# ── Extension UI Routes ───────────────────────────────────────────────────
# Auto-register any routes.py files found in installed extensions.
# Each extension can define a register_routes(rt) function that
# receives the FastHTML route decorator and registers its own routes.
_route_inspector.load_routes(rt)


if __name__ == "__main__":
    serve(reload=False)
