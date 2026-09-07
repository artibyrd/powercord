# mypy: ignore-errors
from __future__ import annotations

import asyncio
import logging
import os
import signal

import httpx
from fasthtml.common import *
from fasthtml.core import APIRouter
from sqlmodel import Session

from app.common.alchemy import init_connection_engine
from app.common.extension_loader import GadgetInspector
from app.db.models import ApiKey
from app.ui.helpers import (
    add_dashboard_admin,
    get_extension_details_modal,
    get_guild_cogs,
    get_guild_sprockets,
    get_guild_widgets,
    get_internal_api_client,
    is_dashboard_admin,
    notify_api_of_config_change,
    remove_dashboard_admin,
    update_guild_extension_setting,
)

admin_actions_router = APIRouter()


@admin_actions_router("/admin/examples/counters/start", methods=["POST"])
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


@admin_actions_router("/admin/examples/counters/stop", methods=["POST"])
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


@admin_actions_router("/admin/manage/add", methods=["POST"])
async def add_admin_route(req, sess):
    from app.ui.routes.admin import _render_admin_list

    form = await req.form()
    try:
        user_id = int(form.get("user_id"))
        comment = form.get("comment")
        add_dashboard_admin(user_id, comment)
    except ValueError:
        pass

    return await _render_admin_list(sess)


@admin_actions_router("/admin/manage/remove", methods=["POST"])
async def remove_admin_route(req, sess):
    from app.ui.routes.admin import _render_admin_list

    form = await req.form()
    try:
        user_id = int(form.get("user_id"))
        remove_dashboard_admin(user_id)
    except ValueError:
        pass

    return await _render_admin_list(sess)


@admin_actions_router("/admin/api-key/toggle", methods=["POST"])
async def toggle_api_key_route(req, sess):
    from app.ui.routes.admin import _render_admin_api_keys

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


@admin_actions_router("/admin/extensions/reload", methods=["POST"])
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


@admin_actions_router("/admin/extensions/toggle", methods=["POST"])
async def toggle_gadget_route(req):
    """Handles toggling an extension on/off globally (guild_id=0)."""
    from app.ui.routes.admin import extension_card

    form_data = await req.form()
    extension_name = form_data.get("extension_name")
    is_enabled = form_data.get("enabled") == "on"
    guild_id = 0

    logging.info(f"Toggle global: Ext={extension_name} Enabled={is_enabled}")

    inspector = GadgetInspector()
    all_extensions = inspector.inspect_extensions()
    gadgets = all_extensions.get(extension_name, [])

    for g_type in gadgets:
        update_guild_extension_setting(guild_id, extension_name, g_type, is_enabled)

    status_msg = ""
    if "cog" in gadgets:
        try:
            async with get_internal_api_client() as client:
                check_resp = await client.get(
                    f"http://127.0.0.1:8001/extensions/{extension_name}/hotload-check", timeout=3.0
                )
                requires_restart = False
                if check_resp.status_code == 200:
                    requires_restart = check_resp.json().get("requires_restart", False)

                if requires_restart:
                    status_msg = "⚠️ Restart required for this cog."
                elif is_enabled:
                    resp = await client.post(f"http://127.0.0.1:8001/extensions/{extension_name}/reload", timeout=5.0)
                    if resp.status_code == 200:
                        status_msg = "✅ Loaded"
                    else:
                        status_msg = f"⚠️ Load failed: {resp.text}"
                else:
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

    enabled_cogs = get_guild_cogs(0)
    enabled_sprockets = get_guild_sprockets(0)
    enabled_widgets = get_guild_widgets(0)

    card = extension_card(extension_name, gadgets, enabled_cogs, enabled_sprockets, enabled_widgets)

    if status_msg:
        return card, Div(status_msg, id=f"status-{extension_name}", cls="text-xs mr-2", hx_swap_oob="true")

    return card


@admin_actions_router("/admin/bot/restart", methods=["POST"])
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


@admin_actions_router("/admin/api/restart", methods=["POST"])
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


@admin_actions_router("/admin/ui/restart", methods=["POST"])
async def restart_ui_action(req):
    """Restarts the UI process gracefully."""
    logging.info("UI: Received restart request. Exiting...")

    async def _kill():
        await asyncio.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_kill())
    return P("UI restart initiated.", style="color: green;")


@admin_actions_router("/admin/system/restart", methods=["POST"])
async def restart_system_action(req):
    """Restarts Bot, API, and UI."""
    msgs = []

    try:
        async with get_internal_api_client() as client:
            await client.post("http://127.0.0.1:8001/bot/restart", timeout=2.0)
        msgs.append("Bot restarted.")
    except Exception:
        msgs.append("Bot restart initiated.")

    try:
        async with get_internal_api_client() as client:
            await client.post("http://127.0.0.1:8000/restart", timeout=2.0)
        msgs.append("API restarted.")
    except Exception:
        msgs.append("API restart initiated.")

    async def _kill():
        await asyncio.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_kill())
    msgs.append("UI restart initiated.")

    return P("All system restarts initiated.", style="color: green;")


@admin_actions_router("/admin/extensions/{extension_name}/details", methods=["GET"])
async def extension_details_route(extension_name: str, req):
    """Returns a modal with the extension details (Global admin)."""
    auth_data = req.session.get("auth", {})
    token_data = auth_data.get("token_data", {})
    access_token = token_data.get("access_token")
    return get_extension_details_modal(extension_name, access_token=access_token)
