import asyncio
import functools
import logging
import os
import sys
from pathlib import Path

import httpx
from fasthtml.common import FT, H3, A, Button, Dialog, Div, Form, I, P, Script, Span

# Add the project root directory to the Python path to ensure consistent imports
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))  # noqa: E402


from typing import Any, Callable

from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.common.extension_loader import GadgetInspector
from app.db.db_tools import get_or_create_internal_key
from app.db.models import AdminUser, GuildExtensionSettings, WidgetSettings
from app.ui.auth import get_bot_guild_ids, get_user_guilds

SCOPE_PUBLIC = 0
SCOPE_ADMIN_DASHBOARD = 1


def get_internal_api_client() -> httpx.AsyncClient:
    """Returns an httpx.AsyncClient configured with the internal API key."""
    key = get_or_create_internal_key()
    return httpx.AsyncClient(headers={"Authorization": f"Bearer {key}"})


def get_widget_name(widget: Callable | FT) -> str | None:
    """
    Safely gets the name of a widget, which can be a function,
    a functools.partial, or a pre-rendered FT object.
    For FT objects, the 'id' attribute is used as the name.
    """
    if isinstance(widget, functools.partial):
        return widget.func.__name__
    # FT objects do not have a __name__, but may have an id.
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


def add_dashboard_admin(user_id: int, comment: str | None = None):
    """Adds a new dashboard admin."""
    engine = init_connection_engine()
    with Session(engine) as session:
        if session.get(AdminUser, user_id):
            return  # Already exists
        admin = AdminUser(user_id=user_id, comment=comment)
        session.add(admin)
        session.commit()


def remove_dashboard_admin(user_id: int):
    """Removes a dashboard admin."""
    engine = init_connection_engine()
    with Session(engine) as session:
        admin = session.get(AdminUser, user_id)
        if admin:
            session.delete(admin)
            session.commit()


async def get_discord_username(user_id: int) -> str:
    """Fetches a Discord username from the API using the bot token."""
    bot_token = os.getenv("DISCORD_TOKEN")
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


def is_gadget_enabled(guild_id: int, extension_name: str, gadget_type: str) -> bool:
    """
    Checks if a gadget is enabled.
    Hierarchy:
    1. Global (guild_id=0) MUST be enabled.
    2. If Global is enabled, check Local (guild_id) setting.
       - If Local setting exists, use it.
       - If Local setting does NOT exist, default to True (inherit Global).
    """
    engine = init_connection_engine()
    try:
        with Session(engine) as session:
            # 1. Check Global Setting
            global_stmt = select(GuildExtensionSettings).where(
                GuildExtensionSettings.guild_id == 0,
                GuildExtensionSettings.extension_name == extension_name,
                GuildExtensionSettings.gadget_type == gadget_type,
            )
            global_setting = session.exec(global_stmt).first()

            # If global setting is explicitly disabled or missing, return False
            # (Default to Disabled for safety/cleanliness if no record exists)
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

            # If local setting exists, respect it (it can only toggle OFF, since we passed Global check)
            if local_setting:
                return local_setting.is_enabled

            # If no local setting, default to True (since Global is Enabled)
            return True

    except Exception as e:
        logging.error(f"Error checking enabled status for {extension_name} ({gadget_type}) in guild {guild_id}: {e}")
        return False


def _get_enabled_gadgets(guild_id: int, gadget_type: str) -> list[str]:
    """
    Helper to get enabled gadgets of a specific type for a guild.
    Returns a list of extension names that are enabled effectively.
    """
    # This is a bit inefficient (N+1-ish) but safe for now.
    # Can be optimized with a single complex query if performance becomes an issue.
    # We need to know ALL potential extensions to check them.
    # Alternatively, we can just query the DB for what IS enabled.

    engine = init_connection_engine()
    enabled_gadgets = []

    # Get all globally enabled extensions of this type
    try:
        with Session(engine) as session:
            global_stmt = select(GuildExtensionSettings).where(
                GuildExtensionSettings.guild_id == 0,
                GuildExtensionSettings.gadget_type == gadget_type,
            )
            all_global = session.exec(global_stmt).all()
            # Explicitly access model properties for reliable behavior across DB dialects
            globally_enabled = [row.extension_name for row in all_global if row.is_enabled]

            if guild_id == 0:
                return globally_enabled

            # Filter by local settings
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
    settings = {}

    try:
        with Session(engine) as session:
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
                }
    except Exception as e:
        logging.error(f"Error fetching widget settings: {e}")

    return settings


def update_widget_setting(guild_id: int, extension_name: str, widget_name: str, setting: str, value: Any):
    """Update a widget setting in the database."""
    logging.info(f"DATABASE: Setting widget '{extension_name}.{widget_name}' for guild {guild_id}: {setting}={value}")

    engine = init_connection_engine()
    try:
        with Session(engine) as session:
            # Check if the record exists
            statement = select(WidgetSettings).where(
                WidgetSettings.guild_id == guild_id,
                WidgetSettings.extension_name == extension_name,
                WidgetSettings.widget_name == widget_name,
            )
            widget_setting = session.exec(statement).first()

            if not widget_setting:
                # Create new record with defaults
                widget_setting = WidgetSettings(
                    guild_id=guild_id,
                    extension_name=extension_name,
                    widget_name=widget_name,
                )

            # Update the specific setting
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


def update_guild_extension_setting(guild_id: int, extension_name: str, gadget_type: str, is_enabled: bool):
    """Update a guild extension setting (enable/disable) in the database."""
    logging.info(f"DATABASE: Setting {gadget_type} '{extension_name}' for guild {guild_id}: enabled={is_enabled}")

    engine = init_connection_engine()
    try:
        with Session(engine) as session:
            # Check if the record exists
            statement = select(GuildExtensionSettings).where(
                GuildExtensionSettings.guild_id == guild_id,
                GuildExtensionSettings.extension_name == extension_name,
                GuildExtensionSettings.gadget_type == gadget_type,
            )
            extension_setting = session.exec(statement).first()

            if not extension_setting:
                # Create new record
                extension_setting = GuildExtensionSettings(
                    guild_id=guild_id, extension_name=extension_name, gadget_type=gadget_type, is_enabled=is_enabled
                )
                session.add(extension_setting)
            else:
                # Update existing record
                extension_setting.is_enabled = is_enabled
                session.add(extension_setting)

            session.commit()
            session.refresh(extension_setting)
            logging.info(f"Successfully updated {gadget_type} '{extension_name}' enabled status to {is_enabled}")

    except Exception as e:
        logging.error(f"Error updating extension setting: {e}", exc_info=True)


async def get_admin_guilds(user_access_token: str, user_id: int) -> dict[str, dict]:
    """Fetches guilds where the user is an admin or has a DashboardAccessRole and the bot is present."""
    ADMIN_PERM = 1 << 3
    bot_token = os.getenv("DISCORD_TOKEN")
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
        user_guilds, bot_guild_ids = await asyncio.gather(
            get_user_guilds(user_access_token), get_bot_guild_ids(bot_token)
        )
        logging.info(f"Fetched {len(user_guilds)} user guilds and {len(bot_guild_ids)} bot guilds.")
    except Exception as e:
        logging.error(f"Error fetching guilds in get_admin_guilds: {e}", exc_info=True)
        raise e

    # Fetch dashboard access roles from DB
    from app.db.models import DashboardAccessRole

    engine = init_connection_engine()
    with Session(engine) as session:
        stmt = select(DashboardAccessRole)
        roles = session.exec(stmt).all()

    # Map guild_id -> list of allowed role_ids
    allowed_roles_by_guild: dict[str, set[str]] = {}
    for r in roles:
        gid_str = str(r.guild_id)
        if gid_str not in allowed_roles_by_guild:
            allowed_roles_by_guild[gid_str] = set()
        allowed_roles_by_guild[gid_str].add(str(r.role_id))

    admin_guilds = {}
    for g in user_guilds:
        gid = g["id"]
        if gid not in bot_guild_ids:
            continue

        has_access = False
        # Check Admin perm
        if int(g["permissions"]) & ADMIN_PERM:
            has_access = True
        elif gid in allowed_roles_by_guild:
            # Check Bot API for user roles in this guild
            try:
                async with get_internal_api_client() as client:
                    resp = await client.get(f"http://127.0.0.1:8001/user/{user_id}/guilds/{gid}/roles", timeout=2.0)
                    if resp.status_code == 200:
                        user_role_ids = {str(r) for r in resp.json().get("roles", [])}
                        if allowed_roles_by_guild[gid].intersection(user_role_ids):
                            has_access = True
            except Exception as e:
                logging.error(f"Failed to fetch roles for user {user_id} in guild {gid}: {e}")

        if has_access:
            admin_guilds[gid] = g

    logging.info(f"Found {len(admin_guilds)} shared guilds with dashboard access.")
    return admin_guilds


async def notify_api_of_config_change(guild_id: int):
    """Sends a notification to the API to reload its configuration for a specific guild."""
    api_reload_url = os.getenv("API_RELOAD_URL")
    api_reload_key = os.getenv("API_RELOAD_KEY")

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


async def notify_bot_of_config_change(guild_id: int):
    """Sends a notification to the bot to reload its configuration for a specific guild."""
    bot_reload_url = os.getenv("BOT_RELOAD_URL", "http://127.0.0.1:8001/config/reload")

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


def get_extension_details_modal(extension_name: str, access_token: str | None = None) -> FT:
    """Generates a modal containing the extension's README and functionality breakdown."""
    inspector = GadgetInspector()
    extensions_report = inspector.inspect_extensions()
    gadgets = extensions_report.get(extension_name, [])

    # Badges for functionality
    badges = []
    if "cog" in gadgets:
        badges.append(Span("Cog", cls="badge badge-primary badge-sm font-bold shadow-md"))
    if "sprocket" in gadgets:
        badges.append(Span("Sprocket", cls="badge badge-secondary badge-sm font-bold shadow-md"))
    if "widget" in gadgets:
        badges.append(Span("Widget", cls="badge badge-accent badge-sm font-bold shadow-md"))

    # Load README if it exists
    readme_path = inspector.extensions_dir / extension_name / "README.md"
    readme_content = ""
    import json

    if readme_path.is_file():
        try:
            readme_content = readme_path.read_text(encoding="utf-8")
            # Escape newlines and quotes for JS injection
            readme_content = json.dumps(readme_content)
        except Exception as e:
            logging.error(f"Failed to read README for {extension_name}: {e}")
            readme_content = json.dumps("*Failed to load README.*")
    else:
        readme_content = json.dumps("*No README.md found for this extension.*")

    modal_id = f"modal-{extension_name}-details"

    close_button = Form(
        Button(I(cls="fa-solid fa-xmark"), cls="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"),
        method="dialog",
    )

    header_elements = [H3(f"{extension_name.capitalize()} Details", cls="font-bold text-2xl flex-grow")]

    if "sprocket" in gadgets:
        href_url = f"http://localhost:8000/docs#/{extension_name}"
        if access_token:
            href_url = f"http://localhost:8000/docs?token={access_token}#/{extension_name}"

        docs_link = A(
            I(cls="fa-solid fa-book"),
            " API Docs",
            href=href_url,
            target="_blank",
            cls="btn btn-ghost btn-outline btn-sm text-info ml-4",
            title="API Docs",
        )
        header_elements.append(docs_link)

    modal_content = Div(
        close_button,
        Div(*header_elements, cls="flex items-center w-full pr-8 mb-2"),
        Div(*badges, cls="flex gap-2 mb-6")
        if badges
        else P("No explicit gadgets loaded.", cls="text-sm opacity-50 mb-6"),
        Div(
            Div(id=f"readme-{extension_name}", cls="prose prose-sm prose-invert max-w-none"),
            cls="bg-base-300 p-4 rounded-lg border border-base-content/10 shadow-inner max-h-[60vh] overflow-y-auto",
        ),
        # Use marked.js to render the markdown
        Script(f"document.getElementById('readme-{extension_name}').innerHTML = marked.parse({readme_content});"),
        cls="modal-box w-11/12 max-w-3xl bg-base-100 shadow-2xl border border-secondary/20",
    )

    return Dialog(
        modal_content,
        Form(method="dialog", cls="modal-backdrop", children=[Button("close")]),
        id=modal_id,
        cls="modal modal-bottom sm:modal-middle",
        # Auto-open when injected
        open=True,
    )
