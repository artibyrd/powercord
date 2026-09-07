# mypy: ignore-errors
from __future__ import annotations

import logging

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.db.models import ApiUserRole, DashboardAccessRole, DiscordRole
from app.ui.helpers import get_admin_guilds, get_internal_api_client


async def _check_guild_admin(guild_id: int, req) -> bool:
    session = getattr(req, "session", None)
    if session is None or not isinstance(session, dict):
        return False
    auth = session.get("auth", {})
    if not isinstance(auth, dict):
        return False
    user_access_token = (
        auth.get("token_data", {}).get("access_token") if isinstance(auth.get("token_data"), dict) else None
    )
    if not user_access_token:
        return False
    user_id_str = auth.get("id")
    if not user_id_str:
        return False
    try:
        user_id = int(user_id_str)
        from app.ui.helpers import is_dashboard_admin

        if is_dashboard_admin(user_id):
            return True
        admin_guilds = await get_admin_guilds(user_access_token, user_id)
        guild = admin_guilds.get(str(guild_id), {})
        return guild.get("owner", False) or (int(guild.get("permissions", 0)) & (1 << 3)) != 0
    except Exception:
        return False


async def _get_guild_roles(guild_id: int) -> tuple[list[dict], bool]:
    """Fetch roles for a guild.

    First queries the Bot Internal API. If unavailable or empty, falls back
    to cached DiscordRole records in the database.
    Returns (roles_list, is_live_from_bot).
    """
    from app.bot.internal_server import get_bot_api_url

    guild_roles = []
    is_live = False
    try:
        async with get_internal_api_client() as client:
            resp = await client.get(get_bot_api_url(f"/guilds/{guild_id}/roles"), timeout=2.0)
            if resp.status_code == 200:
                fetched = resp.json().get("roles", [])
                if fetched:
                    guild_roles = fetched
                    is_live = True
    except Exception as e:
        logging.debug(f"Failed to fetch live guild roles for {guild_id}: {e}")

    if not guild_roles:
        engine = init_connection_engine()
        with Session(engine) as session:
            db_roles = session.exec(
                select(DiscordRole).where(DiscordRole.guild_id == guild_id).order_by(DiscordRole.position.desc())
            ).all()
            if db_roles:
                guild_roles = [{"id": str(r.id), "name": r.name} for r in db_roles if not r.is_managed]

    return guild_roles, is_live


async def _render_access_roles(guild_id: int) -> FT:
    guild_roles, is_live = await _get_guild_roles(guild_id)

    engine = init_connection_engine()
    with Session(engine) as session:
        stmt = select(DashboardAccessRole).where(DashboardAccessRole.guild_id == guild_id)
        saved_roles = session.exec(stmt).all()
        saved_role_ids = {str(r.role_id) for r in saved_roles}

    active_role_badges = []
    for r in saved_roles:
        role_name = f"Role {r.role_id}"
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

    if available_roles:
        role_input = Select(
            Option("Select a role...", value="", disabled=True, selected=True),
            *[Option(r["name"], value=r["id"]) for r in available_roles],
            name="role_id",
            cls="select select-bordered select-sm w-full max-w-xs mr-2",
        )
        status_msg = ""
    elif guild_roles and not available_roles:
        role_input = Input(
            type="text",
            name="role_id_manual",
            placeholder="Enter Role Snowflake ID...",
            cls="input input-bordered input-sm w-64 mr-2",
        )
        status_msg = P("All available roles have been granted access.", cls="text-sm text-success mt-2")
    else:
        role_input = Input(
            type="text",
            name="role_id_manual",
            placeholder="Enter Role Snowflake ID...",
            cls="input input-bordered input-sm w-64 mr-2",
        )
        status_msg = P(
            "⚠️ No server roles found in cache. Ensure the bot is connected to synchronize server roles.",
            cls="text-sm text-warning mt-2",
        )

    cache_notice = (
        Span(" (Loaded from DB cache)", cls="text-xs italic opacity-70") if (not is_live and guild_roles) else ""
    )

    add_role_form = Form(
        Div(
            role_input,
            Button("Grant Access", cls="btn btn-primary btn-sm"),
            cls="flex items-center flex-wrap gap-2 mt-4",
        ),
        status_msg,
        hx_post=f"/dashboard/{guild_id}/access-roles/add",
        hx_target="#access-roles-container",
        hx_swap="outerHTML",
        id="add-role-form",
    )

    return Div(
        H3("Dashboard Access Roles", cache_notice, cls="text-xl font-bold mb-2"),
        P("Users with these roles can access this server's dashboard.", cls="text-sm opacity-80 mb-4"),
        Div(*active_role_badges, cls="flex gap-2 flex-wrap mb-4")
        if active_role_badges
        else P("No additional roles granted.", cls="text-sm italic opacity-60"),
        add_role_form,
        id="access-roles-container",
        cls="p-4 bg-base-200 rounded-lg shadow-inner mb-8",
    )


async def add_access_role(guild_id: int, req, sess):
    if not await _check_guild_admin(guild_id, req):
        return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    auth = sess.get("auth", {})
    user_access_token = auth.get("token_data", {}).get("access_token")
    if not user_access_token:
        return P("Unauthorized", cls="text-error")

    form = await req.form()
    role_id_str = form.get("role_id") or form.get("role_id_manual")
    if role_id_str and str(role_id_str).strip():
        try:
            role_id = int(str(role_id_str).strip())
            engine = init_connection_engine()
            with Session(engine) as session:
                new_role = DashboardAccessRole(guild_id=guild_id, role_id=role_id)
                session.add(new_role)
                session.commit()
        except ValueError:
            pass

    return await _render_access_roles(guild_id)


async def remove_access_role(guild_id: int, req, sess):
    if not await _check_guild_admin(guild_id, req):
        return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    auth = sess.get("auth", {})
    user_access_token = auth.get("token_data", {}).get("access_token")
    if not user_access_token:
        return P("Unauthorized", cls="text-error")

    form = await req.form()
    role_id_str = form.get("role_id")
    if role_id_str:
        try:
            role_id = int(role_id_str)
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


async def _render_api_user_role(guild_id: int) -> FT:
    guild_roles, is_live = await _get_guild_roles(guild_id)

    engine = init_connection_engine()
    with Session(engine) as session:
        stmt = select(ApiUserRole).where(ApiUserRole.guild_id == guild_id)
        api_user_role = session.exec(stmt).first()

    role_badge = None
    if api_user_role:
        role_name = f"Role {api_user_role.role_id}"
        role_info = next((gr for gr in guild_roles if gr["id"] == str(api_user_role.role_id)), None)
        if role_info:
            role_name = role_info["name"]

        role_badge = Div(
            Span(role_name, cls="mr-2"),
            Form(
                Button(
                    I(cls="fa-solid fa-xmark"),
                    cls="btn btn-ghost btn-xs text-error p-0 border-0 bg-transparent shadow-none hover:bg-transparent",
                ),
                hx_post=f"/dashboard/{guild_id}/api-role/remove",
                hx_target="#api-role-container",
                hx_swap="outerHTML",
                cls="inline flex items-center",
            ),
            cls="badge badge-secondary gap-1 py-3 px-3",
        )

    if not role_badge:
        if guild_roles:
            role_selector = Select(
                Option("Select a role...", value="", disabled=True, selected=True),
                *[Option(r["name"], value=r["id"]) for r in guild_roles],
                name="role_id",
                cls="select select-bordered select-sm w-full max-w-xs mr-2",
            )
        else:
            role_selector = Input(
                type="text",
                name="role_id",
                placeholder="Enter Role Snowflake ID...",
                cls="input input-bordered input-sm w-64 mr-2",
            )

        set_role_form = Form(
            Div(
                role_selector,
                Button("Set API User Role", cls="btn btn-secondary btn-sm"),
                cls="flex items-center flex-wrap gap-2 mt-4",
            ),
            hx_post=f"/dashboard/{guild_id}/api-role/set",
            hx_target="#api-role-container",
            hx_swap="outerHTML",
            id="set-api-role-form",
        )
    else:
        set_role_form = ""

    cache_notice = (
        Span(" (Loaded from DB cache)", cls="text-xs italic opacity-70") if (not is_live and guild_roles) else ""
    )

    return Div(
        H3("API User Role", cache_notice, cls="text-xl font-bold mb-2"),
        P("Users with this role are permitted to generate self-service API keys.", cls="text-sm opacity-80 mb-4"),
        role_badge if role_badge else P("No API User Role configured.", cls="text-sm italic opacity-60"),
        set_role_form,
        id="api-role-container",
        cls="p-4 bg-base-200 rounded-lg shadow-inner mb-8",
    )


async def set_api_role(guild_id: int, req, sess):
    if not await _check_guild_admin(guild_id, req):
        return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    auth = sess.get("auth", {})
    user_access_token = auth.get("token_data", {}).get("access_token")
    if not user_access_token:
        return P("Unauthorized", cls="text-error")

    form = await req.form()
    role_id_str = form.get("role_id")
    if role_id_str:
        try:
            role_id = int(role_id_str)
            engine = init_connection_engine()
            with Session(engine) as session:
                stmt = select(ApiUserRole).where(ApiUserRole.guild_id == guild_id)
                existing = session.exec(stmt).first()
                if existing:
                    existing.role_id = role_id
                    session.add(existing)
                else:
                    new_role = ApiUserRole(guild_id=guild_id, role_id=role_id)
                    session.add(new_role)
                session.commit()
        except ValueError:
            pass

    return await _render_api_user_role(guild_id)


async def remove_api_role(guild_id: int, req, sess):
    if not await _check_guild_admin(guild_id, req):
        return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    auth = sess.get("auth", {})
    user_access_token = auth.get("token_data", {}).get("access_token")
    if not user_access_token:
        return P("Unauthorized", cls="text-error")

    engine = init_connection_engine()
    with Session(engine) as session:
        stmt = select(ApiUserRole).where(ApiUserRole.guild_id == guild_id)
        role = session.exec(stmt).first()
        if role:
            session.delete(role)
            session.commit()

    return await _render_api_user_role(guild_id)
