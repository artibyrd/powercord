"""Guild gadget settings, widget configuration, and admin resolution helpers for Powercord.

Governed by:
- inv-500-loc-ceiling: 500 LOC module ceiling
- inv-state-checksum-caching: State caching & invalidation
- inv-view-channel-gating: Permission and role access gating
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any, cast

import httpx
from cachetools import TTLCache  # type: ignore[import-untyped]
from sqlmodel import Session, delete, select

from app.bot.internal_server import get_bot_api_url
from app.common.alchemy import init_connection_engine
from app.common.extension_loader import GadgetInspector
from app.common.extension_manager import EXTENSIONS_DIR, load_manifest
from app.db.db_tools import get_or_create_internal_key
from app.db.models import DashboardAccessRole, GuildExtensionSettings, WidgetSettings
from app.ui.auth import get_bot_guild_ids, get_user_guilds

_admin_guilds_cache: TTLCache = TTLCache(maxsize=1024, ttl=300)


def _get_engine():
    mod_h = sys.modules.get("app.ui.helpers")
    if mod_h and hasattr(mod_h, "init_connection_engine"):
        return mod_h.init_connection_engine()
    return init_connection_engine()


def _get_session():
    mod_h = sys.modules.get("app.ui.helpers")
    if mod_h and hasattr(mod_h, "Session"):
        return mod_h.Session
    return Session


def _gh(name: str, default: Any = None) -> Any:
    mod_h = sys.modules.get("app.ui.helpers")
    if mod_h and hasattr(mod_h, name):
        return getattr(mod_h, name)
    return default


def get_internal_api_client() -> httpx.AsyncClient:
    """Returns an httpx.AsyncClient configured with the internal API key."""
    key = get_or_create_internal_key()
    return httpx.AsyncClient(headers={"Authorization": f"Bearer {key}"})


def seed_global_settings_if_empty(session: Session) -> None:
    """Checks if there are any extension settings for guild_id=0.

    If empty, provisions defaults for all cogs, widgets, sprockets.
    """
    existing = session.exec(select(GuildExtensionSettings).where(GuildExtensionSettings.guild_id == 0)).first()
    if existing:
        return

    inspector = GadgetInspector()
    all_extensions = inspector.inspect_extensions()

    for ext_name, gadgets in all_extensions.items():
        # Check if default_disabled: true in manifest
        ext_path = EXTENSIONS_DIR / ext_name
        default_disabled = False
        if ext_path.exists():
            try:
                manifest = load_manifest(ext_path)
                default_disabled = manifest.get("default_disabled", False)
            except Exception as e:
                logging.error(f"Error loading manifest for {ext_name} during seeding: {e}")

        is_enabled = not default_disabled

        # Add setting for each gadget type
        for g_type in gadgets:
            g_setting = GuildExtensionSettings(
                guild_id=0,
                extension_name=ext_name,
                gadget_type=g_type,
                is_enabled=is_enabled,
            )
            session.add(g_setting)

            # Symmetrically provision default widgets in WidgetSettings if it's enabled
            if g_type == "widget" and is_enabled:
                if ext_path.exists():
                    try:
                        manifest = load_manifest(ext_path)
                        default_widgets = manifest.get("default_widgets", [])
                        for dw in default_widgets:
                            widget_name = dw.get("widget_name")
                            display_order = dw.get("display_order", 99)
                            column_span = dw.get("column_span", 4)
                            position_config = dw.get("position_config", None)

                            w_stmt = select(WidgetSettings).where(
                                WidgetSettings.guild_id == 0,
                                WidgetSettings.extension_name == ext_name,
                                WidgetSettings.widget_name == widget_name,
                            )
                            existing_widget = session.exec(w_stmt).first()
                            if not existing_widget:
                                new_widget = WidgetSettings(
                                    guild_id=0,
                                    extension_name=ext_name,
                                    widget_name=widget_name,
                                    is_enabled=True,
                                    display_order=display_order,
                                    column_span=column_span,
                                    position_config=position_config,
                                )
                                session.add(new_widget)
                    except Exception as e:
                        logging.error(f"Error seeding default widgets for {ext_name}: {e}")

    session.commit()


def is_gadget_enabled(guild_id: int, extension_name: str, gadget_type: str) -> bool:
    """Checks if a gadget is enabled.

    Hierarchy:
    1. Global (guild_id=0) MUST be enabled.
    2. If Global is enabled, check Local (guild_id) setting.
       - If Local setting exists, use it.
       - If Local setting does NOT exist, default to True (inherit Global).
    """
    engine = init_connection_engine()
    try:
        with Session(engine) as session:
            seed_global_settings_if_empty(session)
            # 1. Check Global Setting
            global_stmt = select(GuildExtensionSettings).where(
                GuildExtensionSettings.guild_id == 0,
                GuildExtensionSettings.extension_name == extension_name,
                GuildExtensionSettings.gadget_type == gadget_type,
            )
            global_setting = session.exec(global_stmt).first()

            # If global setting is explicitly disabled or missing, return False
            if not global_setting or not global_setting.is_enabled:
                return False

            # If we are only checking global status (guild_id=0), we are done.
            if guild_id == 0:
                return True

            # 2. Check Local Setting
            local_stmt = select(GuildExtensionSettings).where(
                GuildExtensionSettings.guild_id == guild_id,
                GuildExtensionSettings.extension_name == extension_name,
                GuildExtensionSettings.gadget_type == gadget_type,
            )
            local_setting = session.exec(local_stmt).first()

            # If local setting exists, respect it
            if local_setting:
                return local_setting.is_enabled

            # If no local setting, default to True (inherit Global)
            return True

    except Exception as e:
        logging.error(f"Error checking enabled status for {extension_name} ({gadget_type}) in guild {guild_id}: {e}")
        return False


def _get_enabled_gadgets(guild_id: int, gadget_type: str) -> list[str]:
    """Helper to get enabled gadgets of a specific type for a guild.

    Returns a list of extension names that are enabled effectively.
    """
    engine = init_connection_engine()
    enabled_gadgets: list[str] = []

    try:
        with Session(engine) as session:
            seed_global_settings_if_empty(session)
            global_stmt = select(GuildExtensionSettings).where(
                GuildExtensionSettings.guild_id == 0,
                GuildExtensionSettings.gadget_type == gadget_type,
            )
            all_global = session.exec(global_stmt).all()
            globally_enabled = [row.extension_name for row in all_global if row.is_enabled]

            if guild_id == 0:
                return globally_enabled

            for ext_name in globally_enabled:
                if is_gadget_enabled(guild_id, ext_name, gadget_type):
                    enabled_gadgets.append(ext_name)

    except Exception as e:
        logging.error(f"Error fetching enabled {gadget_type}s for guild {guild_id}: {e}")

    return enabled_gadgets


def get_guild_cogs(guild_id: int) -> list[str]:
    """Get enabled cogs for a guild from the database."""
    return _get_enabled_gadgets(guild_id, "cog")


def get_guild_sprockets(guild_id: int) -> list[str]:
    """Get enabled sprockets for a guild from the database."""
    return _get_enabled_gadgets(guild_id, "sprocket")


def get_guild_widgets(guild_id: int) -> list[str]:
    """Get enabled widgets for a guild from the database."""
    return _get_enabled_gadgets(guild_id, "widget")


def get_widget_settings(guild_id: int) -> dict[str, dict]:
    """Get widget settings for a guild (or global: 0) from the database."""
    engine = init_connection_engine()
    settings: dict[str, dict] = {}

    try:
        with Session(engine) as session:
            seed_global_settings_if_empty(session)
            statement = select(WidgetSettings).where(WidgetSettings.guild_id == guild_id)
            results = session.exec(statement).all()

            for row in results:
                settings[row.widget_name] = {
                    "is_enabled": row.is_enabled,
                    "display_order": row.display_order,
                    "column_span": row.column_span,
                    "grid_x": row.grid_x,
                    "grid_y": row.grid_y,
                    "extension_name": row.extension_name,
                    "position_config": row.position_config,
                }
    except Exception as e:
        logging.error(f"Error fetching widget settings: {e}")

    return settings


def update_widget_setting(guild_id: int, extension_name: str, widget_name: str, setting: str, value: Any) -> None:
    """Update a widget setting in the database."""
    logging.info(f"DATABASE: Setting widget '{extension_name}.{widget_name}' for guild {guild_id}: {setting}={value}")

    engine = init_connection_engine()
    try:
        with Session(engine) as session:
            statement = select(WidgetSettings).where(
                WidgetSettings.guild_id == guild_id,
                WidgetSettings.extension_name == extension_name,
                WidgetSettings.widget_name == widget_name,
            )
            widget_setting = session.exec(statement).first()

            if not widget_setting:
                widget_setting = WidgetSettings(
                    guild_id=guild_id,
                    extension_name=extension_name,
                    widget_name=widget_name,
                )

            if hasattr(widget_setting, setting):
                setattr(widget_setting, setting, value)
                session.add(widget_setting)
                session.commit()
                session.refresh(widget_setting)
                logging.info(f"Successfully updated {setting} to {value} for {widget_name}")
            else:
                logging.error(f"Invalid setting '{setting}' for WidgetSettings")

    except Exception as e:
        logging.error(f"Error updating widget setting: {e}")


def update_guild_extension_setting(guild_id: int, extension_name: str, gadget_type: str, is_enabled: bool) -> None:
    """Update a guild extension setting (enable/disable) in the database."""
    logging.info(f"DATABASE: Setting {gadget_type} '{extension_name}' for guild {guild_id}: enabled={is_enabled}")

    engine = _get_engine()
    try:
        with _get_session()(engine) as session:
            statement = select(GuildExtensionSettings).where(
                GuildExtensionSettings.guild_id == guild_id,
                GuildExtensionSettings.extension_name == extension_name,
                GuildExtensionSettings.gadget_type == gadget_type,
            )
            extension_setting = session.exec(statement).first()

            if not extension_setting:
                extension_setting = GuildExtensionSettings(
                    guild_id=guild_id, extension_name=extension_name, gadget_type=gadget_type, is_enabled=is_enabled
                )
                session.add(extension_setting)
            else:
                extension_setting.is_enabled = is_enabled
                session.add(extension_setting)

            if gadget_type == "widget":
                if is_enabled:
                    ext_path = EXTENSIONS_DIR / extension_name
                    if ext_path.exists():
                        try:
                            manifest = load_manifest(ext_path)
                            default_widgets = manifest.get("default_widgets", [])
                            for dw in default_widgets:
                                widget_name = dw.get("widget_name")
                                display_order = dw.get("display_order", 99)
                                column_span = dw.get("column_span", 4)

                                w_stmt = select(WidgetSettings).where(
                                    WidgetSettings.guild_id == guild_id,
                                    WidgetSettings.extension_name == extension_name,
                                    WidgetSettings.widget_name == widget_name,
                                )
                                existing_widget = session.exec(w_stmt).first()
                                if not existing_widget:
                                    position_config = dw.get("position_config", None)
                                    new_widget = WidgetSettings(
                                        guild_id=guild_id,
                                        extension_name=extension_name,
                                        widget_name=widget_name,
                                        is_enabled=True,
                                        display_order=display_order,
                                        column_span=column_span,
                                        position_config=position_config,
                                    )
                                    session.add(new_widget)
                        except Exception as e:
                            logging.error(f"Error loading manifest or provisioning default widgets: {e}")
                else:
                    delete_stmt = delete(WidgetSettings).where(
                        cast(Any, WidgetSettings.guild_id) == guild_id,
                        cast(Any, WidgetSettings.extension_name) == extension_name,
                    )
                    session.exec(delete_stmt)

            session.commit()
            session.refresh(extension_setting)
            logging.info(f"Successfully updated {gadget_type} '{extension_name}' enabled status to {is_enabled}")

    except Exception as e:
        logging.error(f"Error updating extension setting: {e}", exc_info=True)


async def get_admin_guilds(user_access_token: str, user_id: int) -> dict[str, dict]:
    """Fetches guilds where the user is an admin or has a DashboardAccessRole and the bot is present."""
    user_id = int(user_id)
    if user_access_token != "dev-token":  # noqa: S105
        if user_id in _admin_guilds_cache:
            logging.info(f"Returning cached admin guilds for user {user_id}")
            return cast(dict[str, dict], _admin_guilds_cache[user_id])

    ADMIN_PERM = 1 << 3
    get_env_fn = _gh("os", os).getenv
    bot_token = get_env_fn("POWERCORD_DISCORD_TOKEN")
    if not bot_token:
        raise ValueError("DISCORD_TOKEN is not set.")

    if user_access_token == "dev-token":  # noqa: S105
        logging.info("Skipping Discord fetch for synthetic dev session.")
        return {
            "000000000000000000": {
                "id": "000000000000000000",
                "name": "Dev Synthetic Server",
                "icon": None,
                "permissions": str(ADMIN_PERM),
            }
        }

    logging.info("Fetching admin guilds...")
    try:
        _get_user_guilds = _gh("get_user_guilds", get_user_guilds)
        _get_bot_guild_ids = _gh("get_bot_guild_ids", get_bot_guild_ids)
        user_guilds, bot_guild_ids = await asyncio.gather(
            _get_user_guilds(user_access_token), _get_bot_guild_ids(bot_token)
        )
        logging.info(f"Fetched {len(user_guilds)} user guilds and {len(bot_guild_ids)} bot guilds.")
    except Exception as e:
        logging.error(f"Error fetching guilds in get_admin_guilds: {e}", exc_info=True)
        raise e

    engine = _get_engine()
    with _get_session()(engine) as session:
        stmt = select(DashboardAccessRole)
        roles = session.exec(stmt).all()

    allowed_roles_by_guild: dict[str, set[str]] = {}
    for r in roles:
        gid_str = str(r.guild_id)
        if gid_str not in allowed_roles_by_guild:
            allowed_roles_by_guild[gid_str] = set()
        allowed_roles_by_guild[gid_str].add(str(r.role_id))

    admin_guilds: dict[str, dict] = {}
    for g in user_guilds:
        gid = g["id"]
        if gid not in bot_guild_ids:
            continue

        has_access = False
        if int(g["permissions"]) & ADMIN_PERM:
            has_access = True
        elif gid in allowed_roles_by_guild:
            try:
                async with get_internal_api_client() as client:
                    resp = await client.get(get_bot_api_url(f"/user/{user_id}/guilds/{gid}/roles"), timeout=2.0)
                    if resp.status_code == 200:
                        user_role_ids = {str(r) for r in resp.json().get("roles", [])}
                        if allowed_roles_by_guild[gid].intersection(user_role_ids):
                            has_access = True
            except Exception as e:
                logging.error(f"Failed to fetch roles for user {user_id} in guild {gid}: {e}")

        if has_access:
            admin_guilds[gid] = g

    logging.info(f"Found {len(admin_guilds)} shared guilds with dashboard access.")
    if user_access_token != "dev-token":  # noqa: S105
        _admin_guilds_cache[user_id] = admin_guilds
    return admin_guilds


def restore_default_widget_settings(guild_id: int) -> None:
    """Restore default widget settings for a guild (or global: 0) from manifests."""
    engine = init_connection_engine()
    try:
        with Session(engine) as session:
            delete_stmt = delete(WidgetSettings).where(cast(Any, WidgetSettings.guild_id) == guild_id)
            session.exec(delete_stmt)

            inspector = GadgetInspector()
            all_extensions = inspector.inspect_extensions()

            for ext_name in all_extensions.keys():
                if is_gadget_enabled(guild_id, ext_name, "widget"):
                    ext_path = EXTENSIONS_DIR / ext_name
                    if ext_path.exists():
                        try:
                            manifest = load_manifest(ext_path)
                            default_widgets = manifest.get("default_widgets", [])
                            for dw in default_widgets:
                                widget_name = dw.get("widget_name")
                                display_order = dw.get("display_order", 99)
                                column_span = dw.get("column_span", 4)
                                position_config = dw.get("position_config", None)

                                new_widget = WidgetSettings(
                                    guild_id=guild_id,
                                    extension_name=ext_name,
                                    widget_name=widget_name,
                                    is_enabled=True,
                                    display_order=display_order,
                                    column_span=column_span,
                                    position_config=position_config,
                                )
                                session.add(new_widget)
                        except Exception as e:
                            logging.error(f"Error seeding default widgets for {ext_name} on restore: {e}")
            session.commit()
            logging.info(f"Successfully restored default widget settings for guild {guild_id}")
    except Exception as e:
        logging.error(f"Error restoring default widget settings for guild {guild_id}: {e}")
