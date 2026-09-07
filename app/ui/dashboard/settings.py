# mypy: ignore-errors
from __future__ import annotations

import json

from fasthtml.common import *
from fasthtml.core import APIRouter
from sqlmodel import Session, select
from starlette.responses import Response

from app.common.alchemy import init_connection_engine
from app.db.models import DiscordAuditorConfig, SecurityAlertOverride, UserSetting
from app.ui.dashboard.api_keys import (
    _render_self_service_keys,
    generate_guild_api_key_route,
    revoke_guild_api_key_route,
)
from app.ui.dashboard.roles import (
    _check_guild_admin,
    _get_guild_roles,
    _render_access_roles,
    _render_api_user_role,
    add_access_role,
    remove_access_role,
    remove_api_role,
    set_api_role,
)

settings_router = APIRouter()

# Decorate imported role and key route handlers onto settings_router
settings_router.post("/dashboard/{guild_id:int}/access-roles/add")(add_access_role)
settings_router.post("/dashboard/{guild_id:int}/access-roles/remove")(remove_access_role)
settings_router.post("/dashboard/{guild_id:int}/api-role/set")(set_api_role)
settings_router.post("/dashboard/{guild_id:int}/api-role/remove")(remove_api_role)
settings_router.post("/dashboard/{guild_id:int}/api-key/generate")(generate_guild_api_key_route)
settings_router.post("/dashboard/{guild_id:int}/api-key/revoke")(revoke_guild_api_key_route)

__all__ = [
    "settings_router",
    "_check_guild_admin",
    "_get_guild_roles",
    "_render_access_roles",
    "add_access_role",
    "remove_access_role",
    "_render_api_user_role",
    "set_api_role",
    "remove_api_role",
    "_render_self_service_keys",
    "generate_guild_api_key_route",
    "revoke_guild_api_key_route",
    "toggle_nav_route",
    "post_auditor_settings",
    "post_alert_override",
    "post_alert_override_remove",
]


@settings_router("/dashboard/{guild_id:int}/toggle-nav", methods=["POST"])
async def toggle_nav_route(guild_id: int, req, sess):
    """Handles toggling user visibility preferences (updates UserSetting in the database)."""
    auth = sess.get("auth", {})
    user_id_str = auth.get("id")
    if not user_id_str:
        return Response("Unauthorized", status_code=401)

    try:
        user_id = int(user_id_str)
    except ValueError:
        return Response("Invalid User ID", status_code=400)

    show_topbar_param = req.query_params.get("show_topbar")

    try:
        form_data = await req.form()
        if show_topbar_param is None:
            show_topbar_param = form_data.get("show_topbar")
    except Exception:  # noqa: S110
        pass

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


@settings_router("/dashboard/{guild_id:int}/auditor-settings", methods=["POST"])
async def post_auditor_settings(guild_id: int, req):
    """Parses lowest admin role and staff/announcement channels, validates, and saves in DB."""
    form = await req.form()

    role_id_raw = form.get("staff_separator_role_id")
    staff_separator_role_id = None
    if role_id_raw:
        try:
            staff_separator_role_id = int(role_id_raw)
        except ValueError:
            pass

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


@settings_router("/dashboard/{guild_id:int}/alerts/override", methods=["POST"])
async def post_alert_override(guild_id: int, req):
    """Saves a security alert override to the database and refreshes the page."""
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

    from app.extensions.utilities.widget import SecurityRuleEngine

    SecurityRuleEngine.invalidate(guild_id)

    return Response(headers={"HX-Refresh": "true"})


@settings_router("/dashboard/{guild_id:int}/alerts/override/remove", methods=["POST"])
async def post_alert_override_remove(guild_id: int, req):
    """Deletes a security alert override and refreshes the page."""
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

    from app.extensions.utilities.widget import SecurityRuleEngine

    SecurityRuleEngine.invalidate(guild_id)

    return Response(headers={"HX-Refresh": "true"})
