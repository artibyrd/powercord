import hashlib
import json
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.db.db_tools import get_or_create_internal_key
from app.db.models import (
    AdminUser,
    ApiAccessRole,
    ApiKey,
    DashboardAccessRole,
    GuildExtensionSettings,
)


async def get_current_api_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    token: Annotated[str | None, Query()] = None,
    x_guild_id: Annotated[int | None, Header()] = None,
):
    """
    Unified API authentication dependency.
    Validates Internal API keys, Database API keys, and Discord OAuth tokens.
    Returns a dict with 'identity' and 'scopes'.
    """
    if not authorization and not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization credentials missing")

    if authorization:
        scheme, _, token_val = authorization.partition(" ")
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication scheme")
    else:
        token_val = str(token)

    # 1. Internal System Check
    internal_key = get_or_create_internal_key()
    if token_val == internal_key:
        request.state.user_identity = "system_internal"
        return {"identity": "system_internal", "scopes": ["global.admin"]}

    # 2. Database API Key Check
    engine = init_connection_engine()
    with Session(engine) as session:
        token_hash = hashlib.sha256(token_val.encode("utf-8")).hexdigest()
        api_key = session.exec(select(ApiKey).where(ApiKey.key_hash == token_hash, ApiKey.is_active)).first()
        if api_key:
            try:
                scopes = json.loads(api_key.scopes)
            except json.JSONDecodeError:
                scopes = []
            request.state.user_identity = f"api_key_{api_key.name}"
            return {"identity": f"api_key_{api_key.name}", "scopes": scopes}

    # 3. Discord OAuth Token Check
    async with httpx.AsyncClient() as client:
        # Verify with Discord
        resp = await client.get(
            "https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {token_val}"}, timeout=5.0
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired Discord token")

        user_data = resp.json()
        user_id = int(user_data["id"])

        # Determine scopes based on roles
        user_scopes = set()

        # Grant global access to system admins
        with Session(engine) as session:
            admin_check = session.exec(select(AdminUser).where(AdminUser.user_id == user_id)).first()
            if admin_check:
                user_scopes.add("global.admin")

        # If we have a target guild context, fetch user's roles and verify extension enablement
        if x_guild_id is not None:
            # Query Discord to check if user has admin permission
            guilds_resp = await client.get(
                "https://discord.com/api/users/@me/guilds",
                headers={"Authorization": f"Bearer {token_val}"},
                timeout=5.0,
            )
            if guilds_resp.status_code == 200:
                guilds_data = guilds_resp.json()
                guild_info = next((g for g in guilds_data if str(g.get("id")) == str(x_guild_id)), None)
                if guild_info:
                    perms_str = guild_info.get("permissions", "0")
                    try:
                        perms = int(perms_str)
                    except ValueError:
                        perms = 0
                    if perms & (1 << 3):
                        with Session(engine) as session:
                            enabled_cogs = session.exec(
                                select(GuildExtensionSettings).where(
                                    GuildExtensionSettings.guild_id == x_guild_id,
                                    GuildExtensionSettings.gadget_type == "cog",
                                    GuildExtensionSettings.is_enabled,
                                )
                            ).all()
                            for cog in enabled_cogs:
                                ext = cog.extension_name
                                user_scopes.add(f"{x_guild_id}.{ext}.admin")
                                user_scopes.add(f"{x_guild_id}.{ext}.user")

            roles_resp = await client.get(
                f"http://127.0.0.1:8001/user/{user_id}/guilds/{x_guild_id}/roles",
                headers={"Authorization": f"Bearer {internal_key}"},
                timeout=5.0,
            )
            if roles_resp.status_code == 200:
                user_roles = [int(r) for r in roles_resp.json().get("roles", [])]
                user_roles_set = set(user_roles)

                with Session(engine) as session:
                    # Query DashboardAccessRole and ApiAccessRole tables in DB for this guild
                    dashboard_roles = session.exec(
                        select(DashboardAccessRole).where(DashboardAccessRole.guild_id == x_guild_id)
                    ).all()
                    access_roles = session.exec(select(ApiAccessRole).where(ApiAccessRole.guild_id == x_guild_id)).all()

                    dashboard_role_ids = {dr.role_id for dr in dashboard_roles}
                    if dashboard_role_ids.intersection(user_roles_set):
                        enabled_cogs = session.exec(
                            select(GuildExtensionSettings).where(
                                GuildExtensionSettings.guild_id == x_guild_id,
                                GuildExtensionSettings.gadget_type == "cog",
                                GuildExtensionSettings.is_enabled,
                            )
                        ).all()
                        for cog in enabled_cogs:
                            ext = cog.extension_name
                            user_scopes.add(f"{x_guild_id}.{ext}.user")

                    for ar in access_roles:
                        if ar.role_id in user_roles_set:
                            user_scopes.add(f"{x_guild_id}.{ar.extension_name}.admin")
                            user_scopes.add(f"{x_guild_id}.{ar.extension_name}.user")

        request.state.user_identity = f"discord_user_{user_id}"
        return {"identity": f"discord_user_{user_id}", "scopes": list(user_scopes)}


def api_scope_required(extension: str, level: str = "user"):
    """
    Dependency generator to secure an endpoint to a specific scope.
    Usage: @app.get("/path", dependencies=[Depends(api_scope_required("honeypot", level="admin"))])
    """

    async def scope_checker(
        request: Request,
        user: Annotated[dict, Depends(get_current_api_user)],
    ):
        scopes = user.get("scopes", [])

        # 1. Check super-scopes first
        if "global.admin" in scopes or "core.admin" in scopes or "global" in scopes:
            return user
        if level == "user":
            if "global.user" in scopes or "core.user" in scopes:
                return user

        # 2. Check extension-wide scopes
        if f"global.{extension}.admin" in scopes:
            return user
        if level == "user":
            if f"global.{extension}.user" in scopes:
                return user

        # 3. Resolve guild_id
        guild_id = None
        if request.path_params.get("guild_id"):
            guild_id = str(request.path_params["guild_id"])
        elif request.query_params.get("guild_id"):
            guild_id = str(request.query_params["guild_id"])
        elif request.query_params.get("x_guild_id"):
            guild_id = str(request.query_params["x_guild_id"])
        elif request.headers.get("x-guild-id"):
            guild_id = str(request.headers["x-guild-id"])
        elif request.headers.get("X-Guild-ID"):
            guild_id = str(request.headers["X-Guild-ID"])

        # 4. Check guild-specific scopes if guild_id is resolved
        if guild_id:
            if f"{guild_id}.{extension}.admin" in scopes:
                return user
            if level == "user":
                if f"{guild_id}.{extension}.user" in scopes:
                    return user

        # 5. Check direct fallback (for backward compatibility)
        if extension in scopes:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required scope: {extension}",
        )

    return scope_checker
