# mypy: ignore-errors
import hashlib
import json
import logging
import re
import secrets
import sys
from typing import Any

import sqlmodel
from fasthtml.common import *
from sqlmodel import select

from app.bot.internal_server import get_bot_api_url
from app.common.alchemy import init_connection_engine
from app.common.extension_loader import GadgetInspector
from app.db.models import ApiKey, ApiUserRole
from app.ui.helpers import get_admin_guilds, get_internal_api_client, is_dashboard_admin


def _dh(name: str, default: Any = None) -> Any:
    m = sys.modules.get("app.ui.dashboard")
    if m is not None and hasattr(m, name):
        return getattr(m, name)
    return default


async def _render_self_service_keys(guild_id: int, user_id: int, sess: dict) -> FT:
    is_guild_admin = False
    auth = sess.get("auth", {})
    user_access_token = (
        auth.get("token_data", {}).get("access_token") if isinstance(auth.get("token_data"), dict) else None
    )
    if user_access_token:
        try:
            admin_guilds = await _dh("get_admin_guilds", get_admin_guilds)(user_access_token, user_id)
            guild = admin_guilds.get(str(guild_id), {})
            is_guild_admin = (
                guild.get("owner", False)
                or (int(guild.get("permissions", 0)) & (1 << 3)) != 0
                or _dh("is_dashboard_admin", is_dashboard_admin)(user_id)
            )
        except Exception:
            is_guild_admin = False

    prefix = f"guild_{guild_id}_{user_id}_"
    engine = _dh("init_connection_engine", init_connection_engine)()

    with sqlmodel.Session(engine) as session:
        stmt = select(ApiKey).where(ApiKey.name.startswith(prefix)).where(ApiKey.is_active)
        active_keys = session.exec(stmt).all()

    key_rows = []
    for k in active_keys:
        try:
            scopes_list = json.loads(k.scopes)
        except Exception:
            scopes_list = []
        scopes_str = ", ".join(scopes_list)
        display_name = k.name.removeprefix(prefix)

        key_rows.append(
            Tr(
                Td(display_name, cls="font-mono text-xs opacity-70"),
                Td(scopes_str, cls="text-xs font-semibold"),
                Td(
                    Form(
                        Hidden(name="key_id", value=str(k.id)),
                        Button("Revoke", cls="btn btn-error btn-xs"),
                        hx_post=f"/dashboard/{guild_id}/api-key/revoke",
                        hx_target="#self-service-keys-container",
                        hx_swap="outerHTML",
                    )
                ),
            )
        )

    table = (
        Table(
            Thead(Tr(Th("Key Label"), Th("Scopes"), Th("Action"))),
            Tbody(*key_rows),
            cls="table w-full",
        )
        if key_rows
        else P("You have no active keys for this server.", cls="italic opacity-70 mb-4")
    )

    guild_name = "Server"
    if user_access_token:
        try:
            admin_guilds = await get_admin_guilds(user_access_token, user_id)
            guild = admin_guilds.get(str(guild_id), {})
            guild_name = guild.get("name", "Server")
        except Exception as e:
            logging.error(f"Failed to fetch guild name: {e}")

    inspector = GadgetInspector()
    ext_names = list(inspector.inspect_extensions().keys())
    if "powerloader" in ext_names:
        ext_names.remove("powerloader")

    scope_options = []
    for ext in ext_names:
        scope_options.append((f"{guild_name}: {ext}.user", f"{guild_id}.{ext}.user"))
        if is_guild_admin:
            scope_options.append((f"{guild_name}: {ext}.admin", f"{guild_id}.{ext}.admin"))

    scope_checkboxes = []
    for label, val in scope_options:
        scope_checkboxes.append(
            Label(
                Input(
                    type="checkbox",
                    name="scopes",
                    value=val,
                    cls="checkbox checkbox-primary checkbox-sm",
                ),
                Span(label, cls="ml-3 text-sm font-medium text-base-content/85"),
                cls="flex items-center p-3 bg-base-300/40 border border-base-content/20 rounded-lg cursor-pointer hover:bg-base-300/80 transition-all duration-200 w-full max-w-sm",
            )
        )

    label_input = Input(
        type="text",
        name="label",
        placeholder="Key Label (e.g. my-app)",
        required=True,
        cls="input input-bordered input-sm w-full max-w-xs mb-2",
    )

    show_form_btn = Button(
        I(cls="fa-solid fa-plus mr-2"),
        "Generate API Key",
        cls="btn btn-primary btn-sm mt-2",
        onclick="document.getElementById('key-gen-form').classList.remove('hidden'); this.classList.add('hidden');",
        id="show-keygen-btn",
    )

    generate_form = Form(
        Div(
            Label("Key Label:", cls="label-text mb-1 font-semibold text-xs opacity-70"),
            label_input,
            Label("Select Scopes:", cls="label-text mb-1 font-semibold text-xs opacity-70 mt-2"),
            Div(*scope_checkboxes, cls="grid grid-cols-1 md:grid-cols-2 gap-2 mb-4 max-w-2xl"),
            cls="flex flex-col gap-1",
        ),
        Div(
            Button(I(cls="fa-solid fa-key mr-2"), "Generate Key", cls="btn btn-primary btn-sm"),
            Button(
                "Cancel",
                type="button",
                cls="btn btn-ghost btn-sm",
                onclick="document.getElementById('key-gen-form').classList.add('hidden'); document.getElementById('show-keygen-btn').classList.remove('hidden');",
            ),
            cls="flex items-center gap-2 mt-4",
        ),
        hx_post=f"/dashboard/{guild_id}/api-key/generate",
        hx_target="#self-service-keys-container",
        hx_swap="outerHTML",
        cls="mt-4 hidden p-4 bg-base-300/30 rounded-lg",
        id="key-gen-form",
    )

    return Div(
        H3("Self-Service API Keys", cls="text-xl font-bold mb-2"),
        P("Manage your API keys for this guild. You can have up to 5 active keys.", cls="text-sm opacity-80 mb-4"),
        Div(
            table,
            show_form_btn,
            generate_form,
            cls="card bg-base-100 shadow-sm border border-base-content/20 p-4 mb-8",
        ),
        id="self-service-keys-container",
    )


async def generate_guild_api_key_route(guild_id: int, req, sess):
    auth = sess.get("auth", {})
    user_id = auth.get("id")
    user_access_token = auth.get("token_data", {}).get("access_token")
    if not user_id or not user_access_token:
        return P("Unauthorized", cls="text-error")

    user_roles = set()
    try:
        api_client_fn = _dh("get_internal_api_client", get_internal_api_client)
        async with api_client_fn() as client:
            resp = await client.get(get_bot_api_url(f"/user/{user_id}/guilds/{guild_id}/roles"), timeout=2.0)
            if resp.status_code == 200:
                user_roles = {int(r) for r in resp.json().get("roles", [])}
    except Exception as e:
        logging.error(f"Failed to fetch user roles: {e}")
        return P("Error fetching user roles.", cls="text-error")

    is_guild_admin = False
    if user_access_token and user_id:
        try:
            admin_guilds = await _dh("get_admin_guilds", get_admin_guilds)(user_access_token, int(user_id))
            guild = admin_guilds.get(str(guild_id), {})
            is_guild_admin = (
                guild.get("owner", False)
                or (int(guild.get("permissions", 0)) & (1 << 3)) != 0
                or _dh("is_dashboard_admin", is_dashboard_admin)(int(user_id))
            )
        except Exception:
            is_guild_admin = False

    engine = _dh("init_connection_engine", init_connection_engine)()
    with sqlmodel.Session(engine) as session:
        stmt = select(ApiUserRole).where(ApiUserRole.guild_id == guild_id)
        api_user_role = session.exec(stmt).first()

    has_api_user_role = False
    if api_user_role:
        has_api_user_role = int(api_user_role.role_id) in user_roles

    if not (is_guild_admin or has_api_user_role):
        return P("Forbidden: API User Role or Guild Administrator required.", cls="text-error")

    form = await req.form()
    label = form.get("label", "").strip()
    if not label:
        return P("Error: Key Label is required.", cls="text-error")
    label = re.sub(r"[^a-zA-Z0-9\-_]", "", label)
    if not label:
        return P("Error: Invalid Key Label.", cls="text-error")

    prefix = f"guild_{guild_id}_{user_id}_"
    with sqlmodel.Session(engine) as session:
        stmt = select(ApiKey).where(ApiKey.name.startswith(prefix)).where(ApiKey.is_active)
        active_keys = session.exec(stmt).all()
        if len(active_keys) >= 5:
            add_toast(
                sess,
                "Error: You have reached the maximum limit of 5 active keys for this guild.",
                "error",
                dismiss=True,
            )
            render_keys_fn = _dh("_render_self_service_keys", _render_self_service_keys)
            return await render_keys_fn(guild_id, int(user_id), sess)

    if hasattr(form, "getlist"):
        selected_scopes = form.getlist("scopes")
    else:
        selected_scopes = form.get("scopes", [])
        if not isinstance(selected_scopes, list):
            selected_scopes = [selected_scopes]

    if not selected_scopes:
        return P("Error: At least one scope must be selected.", cls="text-error")

    if any(s.endswith(".admin") for s in selected_scopes):
        is_guild_admin = False
        if user_access_token and user_id:
            try:
                admin_guilds = await _dh("get_admin_guilds", get_admin_guilds)(user_access_token, int(user_id))
                guild = admin_guilds.get(str(guild_id), {})
                is_guild_admin = (int(guild.get("permissions", 0)) & (1 << 3)) != 0
            except Exception:
                is_guild_admin = False
        if not is_guild_admin:
            return P("Forbidden: Non-admins cannot generate keys with admin scopes.", cls="text-error")

    allowed_pattern = re.compile(rf"^{guild_id}\.[a-zA-Z0-9\-_]+\.(user|admin)$")
    validated_scopes = []
    for s in selected_scopes:
        if allowed_pattern.match(s):
            validated_scopes.append(s)
        else:
            return P(f"Error: Scope '{s}' is not allowed for this guild.", cls="text-error")

    new_key = f"pc_{secrets.token_urlsafe(32)}"
    new_key_hash = hashlib.sha256(new_key.encode("utf-8")).hexdigest()
    full_name = f"{prefix}{label}_{secrets.token_hex(4)}"

    with sqlmodel.Session(engine) as session:
        api_key = ApiKey(
            key_hash=new_key_hash,
            name=full_name,
            scopes=json.dumps(validated_scopes),
            is_active=True,
            key_type="user",
            guild_id=guild_id,
        )
        session.add(api_key)
        session.commit()

    add_toast(
        sess,
        f"New API key generated: {new_key} (Copy this now; it will not be displayed again!)",
        "success",
        dismiss=True,
    )

    render_keys_fn = _dh("_render_self_service_keys", _render_self_service_keys)
    return await render_keys_fn(guild_id, int(user_id), sess)


async def revoke_guild_api_key_route(guild_id: int, req, sess):
    auth = sess.get("auth", {})
    user_id = auth.get("id")
    user_access_token = auth.get("token_data", {}).get("access_token")
    if not user_id or not user_access_token:
        return P("Unauthorized", cls="text-error")

    user_roles = set()
    try:
        api_client_fn = _dh("get_internal_api_client", get_internal_api_client)
        async with api_client_fn() as client:
            resp = await client.get(get_bot_api_url(f"/user/{user_id}/guilds/{guild_id}/roles"), timeout=2.0)
            if resp.status_code == 200:
                user_roles = {int(r) for r in resp.json().get("roles", [])}
    except Exception as e:
        logging.error(f"Failed to fetch user roles: {e}")
        return P("Error fetching user roles.", cls="text-error")

    is_guild_admin = False
    if user_access_token and user_id:
        try:
            admin_guilds = await _dh("get_admin_guilds", get_admin_guilds)(user_access_token, int(user_id))
            guild = admin_guilds.get(str(guild_id), {})
            is_guild_admin = (
                guild.get("owner", False)
                or (int(guild.get("permissions", 0)) & (1 << 3)) != 0
                or _dh("is_dashboard_admin", is_dashboard_admin)(int(user_id))
            )
        except Exception:
            is_guild_admin = False

    engine = _dh("init_connection_engine", init_connection_engine)()
    with sqlmodel.Session(engine) as session:
        stmt = select(ApiUserRole).where(ApiUserRole.guild_id == guild_id)
        api_user_role = session.exec(stmt).first()

    has_api_user_role = False
    if api_user_role:
        has_api_user_role = int(api_user_role.role_id) in user_roles

    if not (is_guild_admin or has_api_user_role):
        return P("Forbidden: API User Role or Guild Administrator required.", cls="text-error")

    form = await req.form()
    key_id_str = form.get("key_id")
    if key_id_str:
        try:
            key_id = int(key_id_str)
            with sqlmodel.Session(engine) as session:
                api_key = session.get(ApiKey, key_id)
                prefix = f"guild_{guild_id}_{user_id}_"
                if api_key and api_key.name.startswith(prefix):
                    api_key.is_active = False
                    session.add(api_key)
                    session.commit()
                    add_toast(sess, "API key revoked successfully.", "success", dismiss=True)
        except ValueError:
            pass

    render_keys_fn = _dh("_render_self_service_keys", _render_self_service_keys)
    return await render_keys_fn(guild_id, int(user_id), sess)
