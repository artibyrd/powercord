import json
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.db.db_tools import get_or_create_internal_key
from app.db.models import AdminUser, ApiAccessRole, ApiKey


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
        return {"identity": "system_internal", "scopes": ["global"]}

    # 2. Database API Key Check
    engine = init_connection_engine()
    with Session(engine) as session:
        api_key = session.exec(select(ApiKey).where(ApiKey.key == token_val, ApiKey.is_active)).first()
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
                user_scopes.add("global")

        # If we have a target guild context, fetch user's roles from the Admin API
        if x_guild_id:
            roles_resp = await client.get(
                f"http://127.0.0.1:8001/user/{user_id}/guilds/{x_guild_id}/roles",
                headers={"Authorization": f"Bearer {internal_key}"},
                timeout=5.0,
            )
            if roles_resp.status_code == 200:
                user_roles = [int(r) for r in roles_resp.json().get("roles", [])]

                with Session(engine) as session:
                    # Fetch all ApiAccessRoles for this guild
                    access_roles = session.exec(select(ApiAccessRole).where(ApiAccessRole.guild_id == x_guild_id)).all()

                    for ar in access_roles:
                        if ar.role_id in user_roles:
                            user_scopes.add(ar.extension_name)

        request.state.user_identity = f"discord_user_{user_id}"
        return {"identity": f"discord_user_{user_id}", "scopes": list(user_scopes)}


def api_scope_required(required_scope: str):
    """
    Dependency generator to secure an endpoint to a specific scope.
    Usage: @app.get("/path", dependencies=[Depends(api_scope_required("honeypot"))])
    """

    async def scope_checker(user: Annotated[dict, Depends(get_current_api_user)]):
        scopes = user.get("scopes", [])
        if "global" in scopes:
            return user
        if required_scope not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {required_scope}",
            )
        return user

    return scope_checker
