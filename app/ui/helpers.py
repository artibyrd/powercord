"""UI helper utilities, admin management, and re-exported modular helpers for Powercord.

Governed by:
- inv-500-loc-ceiling: 500 LOC module ceiling
- inv-split-stack-isolation: FastHTML vs FastAPI runtime isolation
"""

from __future__ import annotations

import functools
import logging
import os
import sys
from pathlib import Path
from typing import Callable

import httpx
from fasthtml.common import FT
from sqlmodel import Session, select

# Add project root directory to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))  # noqa: E402

from app.bot.internal_server import get_bot_api_url
from app.common.alchemy import init_connection_engine
from app.db.models import AdminUser
from app.ui.guild_helpers import (
    get_admin_guilds,
    get_guild_cogs,
    get_guild_sprockets,
    get_guild_widgets,
    get_internal_api_client,
    get_widget_settings,
    is_gadget_enabled,
    restore_default_widget_settings,
    seed_global_settings_if_empty,
    update_guild_extension_setting,
    update_widget_setting,
)
from app.ui.modal_helpers import get_extension_details_modal

__all__ = [
    "SCOPE_PUBLIC",
    "SCOPE_ADMIN_DASHBOARD",
    "get_internal_api_client",
    "get_widget_name",
    "get_dashboard_admins",
    "is_dashboard_admin",
    "add_dashboard_admin",
    "remove_dashboard_admin",
    "get_discord_username",
    "seed_global_settings_if_empty",
    "is_gadget_enabled",
    "get_guild_cogs",
    "get_guild_sprockets",
    "get_guild_widgets",
    "get_widget_settings",
    "update_widget_setting",
    "update_guild_extension_setting",
    "get_admin_guilds",
    "notify_api_of_config_change",
    "notify_bot_of_config_change",
    "get_extension_details_modal",
    "restore_default_widget_settings",
]

SCOPE_PUBLIC = 0
SCOPE_ADMIN_DASHBOARD = 1


def get_widget_name(widget: Callable | FT) -> str | None:
    """Safely gets the name of a widget (function, partial, or FT object).

    For FT objects, the 'id' attribute is used as the name.
    """
    if isinstance(widget, functools.partial):
        return widget.func.__name__
    if isinstance(widget, FT):
        return getattr(widget, "id", None)
    if hasattr(widget, "__name__"):
        return widget.__name__
    return None


def get_dashboard_admins() -> list[AdminUser]:
    """Returns a list of all dashboard admins."""
    engine = init_connection_engine()
    with Session(engine) as session:
        return list(session.exec(select(AdminUser)).all())


def is_dashboard_admin(user_id: int) -> bool:
    """Checks if a user is a dashboard admin."""
    engine = init_connection_engine()
    with Session(engine) as session:
        user = session.get(AdminUser, user_id)
        return user is not None


def add_dashboard_admin(user_id: int, comment: str | None = None) -> None:
    """Adds a new dashboard admin."""
    engine = init_connection_engine()
    with Session(engine) as session:
        if session.get(AdminUser, user_id):
            return
        admin = AdminUser(user_id=user_id, comment=comment)
        session.add(admin)
        session.commit()


def remove_dashboard_admin(user_id: int) -> None:
    """Removes a dashboard admin."""
    engine = init_connection_engine()
    with Session(engine) as session:
        admin = session.get(AdminUser, user_id)
        if admin:
            session.delete(admin)
            session.commit()


async def get_discord_username(user_id: int) -> str:
    """Fetches a Discord username from the API using the bot token."""
    bot_token = os.getenv("POWERCORD_DISCORD_TOKEN")
    if not bot_token:
        return "Unknown (No Token)"

    url = f"https://discord.com/api/v10/users/{user_id}"
    headers = {"Authorization": f"Bot {bot_token}"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return str(data.get("username", str(user_id)))
            else:
                logging.error(f"Failed to fetch Discord username for {user_id}: {resp.status_code} {resp.text}")
                return f"N/A ({user_id})"
    except Exception as e:
        logging.error(f"Error fetching Discord username: {e}")
        return "Error"


async def notify_api_of_config_change(guild_id: int) -> None:
    """Sends a notification to the API to reload its configuration for a specific guild."""
    api_reload_url = os.getenv("POWERCORD_API_RELOAD_URL")
    api_reload_key = os.getenv("POWERCORD_API_RELOAD_KEY")

    if not api_reload_url or not api_reload_key:
        logging.warning("API reload URL or key not configured. Skipping notification.")
        return

    payload = {"guild_id": guild_id}

    try:
        async with get_internal_api_client() as client:
            response = await client.post(api_reload_url, json=payload)
            response.raise_for_status()
            logging.info(f"Successfully notified API to reload config for guild {guild_id}.")
    except httpx.RequestError as e:
        logging.error(f"Failed to notify API for guild {guild_id}: {e}")


async def notify_bot_of_config_change(guild_id: int) -> None:
    """Sends a notification to the bot to reload its configuration for a specific guild."""
    bot_reload_url = os.getenv("POWERCORD_BOT_RELOAD_URL", get_bot_api_url("/config/reload"))

    if not bot_reload_url:
        logging.warning("Bot reload URL or key not configured. Skipping notification.")
        return

    payload = {"guild_id": guild_id}

    try:
        async with get_internal_api_client() as client:
            response = await client.post(bot_reload_url, json=payload)
            response.raise_for_status()
            logging.info(f"Successfully notified bot to reload config for guild {guild_id}.")
    except httpx.RequestError as e:
        logging.error(f"Failed to notify bot for guild {guild_id}: {e}")
