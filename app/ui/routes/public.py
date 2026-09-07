# mypy: ignore-errors
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import sys

import httpx
import sqlmodel
from fasthtml.common import *
from fasthtml.core import APIRouter
from sqlmodel import select
from starlette.responses import RedirectResponse


def _ph(name: str, default: Any = None) -> Any:
    m = sys.modules.get("app.main_ui")
    if m is not None and hasattr(m, name):
        return getattr(m, name)
    return default


def _init_engine():
    mod_alchemy = sys.modules.get("app.common.alchemy")
    if mod_alchemy and hasattr(mod_alchemy, "init_connection_engine"):
        return mod_alchemy.init_connection_engine()
    mod_helpers = sys.modules.get("app.ui.helpers")
    if mod_helpers and hasattr(mod_helpers, "init_connection_engine"):
        return mod_helpers.init_connection_engine()
    return init_connection_engine()


def _is_admin(user_id: int) -> bool:
    mod_helpers = sys.modules.get("app.ui.helpers")
    if mod_helpers and hasattr(mod_helpers, "is_dashboard_admin"):
        return mod_helpers.is_dashboard_admin(user_id)
    mod_main = sys.modules.get("app.main_ui")
    if mod_main and hasattr(mod_main, "is_dashboard_admin"):
        return mod_main.is_dashboard_admin(user_id)
    return is_dashboard_admin(user_id)


from app.common.alchemy import init_connection_engine
from app.common.extension_loader import GadgetInspector
from app.db.models import ApiKey
from app.ui.components import Accordion
from app.ui.helpers import (
    get_admin_guilds,
    get_widget_name,
    get_widget_settings,
    is_dashboard_admin,
    is_gadget_enabled,
)
from app.ui.page import DashboardPage

public_router = APIRouter()


def guild_card(guild: dict) -> FT:
    """Renders a card representing a server the user has admin access to."""
    guild_id = guild.get("id")
    icon_hash = guild.get("icon")
    icon_url = (
        f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png"
        if icon_hash
        else "https://cdn.discordapp.com/embed/avatars/0.png"
    )

    return Div(
        Div(
            Div(
                Img(src=icon_url, cls="w-12 h-12 rounded-full flex-shrink-0"),
                Div(
                    H3(guild.get("name", "Unknown Server"), cls="font-bold text-lg line-clamp-2"),
                    Span(f"ID: {guild_id}", cls="text-xs opacity-60 font-mono"),
                    cls="flex-grow min-w-0",
                ),
                cls="flex items-center gap-3 flex-grow min-w-0",
            ),
            A("Configure", href=f"/dashboard/{guild_id}", cls="btn btn-outline btn-primary btn-sm flex-shrink-0"),
            cls="flex items-center justify-between gap-4 p-4",
        ),
        cls="card bg-base-300 shadow-sm border border-base-content/20 rounded-xl",
    )


async def _render_client_keys(sess: dict) -> FT:
    auth = sess.get("auth", {})
    user_id = auth.get("id")
    if not user_id:
        return Div()

    is_admin = False
    try:
        is_admin = _is_admin(int(user_id))
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
    engine = _init_engine()

    with sqlmodel.Session(engine) as session:
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


@public_router("/profile/client-key/generate", methods=["POST"])
async def generate_client_key_route(req, sess):
    auth = sess.get("auth", {})
    user_id = auth.get("id")
    render_keys_fn = _ph("_render_client_keys", _render_client_keys)
    if user_id:
        try:
            is_admin = _is_admin(int(user_id))
        except (ValueError, TypeError):
            is_admin = False

        if not is_admin:
            return await render_keys_fn(sess)

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

        engine = _init_engine()
        with sqlmodel.Session(engine) as session:
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

    return await render_keys_fn(sess)


@public_router("/profile/client-key/revoke", methods=["POST"])
async def revoke_client_key_route(req, sess):
    auth = sess.get("auth", {})
    user_id = auth.get("id")
    render_keys_fn = _ph("_render_client_keys", _render_client_keys)
    if not user_id:
        return await render_keys_fn(sess)

    try:
        is_admin = _is_admin(int(user_id))
    except (ValueError, TypeError):
        is_admin = False

    if not is_admin:
        return await render_keys_fn(sess)

    form = await req.form()
    key_id_str = form.get("key_id")

    if key_id_str:
        try:
            key_id = int(key_id_str)
            engine = _init_engine()
            with sqlmodel.Session(engine) as session:
                api_key = session.get(ApiKey, key_id)
                if api_key and api_key.name.startswith(f"client_{user_id}_"):
                    api_key.is_active = False
                    session.add(api_key)
                    session.commit()
                    add_toast(sess, "Client key revoked successfully.", "success", dismiss=True)
        except ValueError:
            pass

    return await render_keys_fn(sess)


@public_router("/profile")
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
            admin_guilds_fn = _ph("get_admin_guilds", get_admin_guilds)
            admin_guilds = await admin_guilds_fn(user_access_token, user_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                add_toast(sess, "Discord session expired. Please log in again.", "error")
                return RedirectResponse("/logout", status_code=303)
            logging.error(f"Failed to fetch guild information in route: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"Failed to fetch guild information in route: {e}", exc_info=True)

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

    render_keys_fn = _ph("_render_client_keys", _render_client_keys)
    client_keys_section = await render_keys_fn(sess)

    return DashboardPage(
        "Profile",
        H1(f"Welcome, {username}!", cls="text-2xl font-extrabold mb-8"),
        server_list,
        client_keys_section,
        session_data,
        auth=auth,
    )


@public_router("/")
def public_home(sess: dict):
    """The main public-facing page, composed of widgets."""
    inspector = _ph("GadgetInspector", GadgetInspector)()
    all_widgets_by_ext = inspector.inspect_widgets()

    auth = sess.get("auth")

    # For the public page, we use the global layout settings (guild_id=0)
    settings = _ph("get_widget_settings", get_widget_settings)(0)

    # Flatten all widget functions and pair with their settings.
    widget_configs = []
    for ext_name, widget_funcs in all_widgets_by_ext.items():
        if not _ph("is_gadget_enabled", is_gadget_enabled)(0, ext_name, "widget"):
            continue

        for func in widget_funcs:
            widget_name = _ph("get_widget_name", get_widget_name)(func)
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
