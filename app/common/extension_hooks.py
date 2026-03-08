"""Extension lifecycle hook registry for Powercord.

Provides a lightweight mechanism for extensions to register callbacks
for lifecycle events.  Currently supported events:

- ``delete_guild_data`` — purges all extension-specific data for a guild.
- ``on_install``        — called after an extension is installed.
- ``on_uninstall``      — called before an extension is removed.

Usage (in an extension's ``__init__.py``)::

    from app.common.extension_hooks import register_hook

    def _delete_my_data(guild_id: int) -> None:
        # ... wipe guild-specific rows ...

    register_hook("my_extension", "delete_guild_data", _delete_my_data)

The UI and bot layers call ``run_hook`` to execute registered callbacks,
and ``supports_delete_data`` to decide whether to show the button/command.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from sqlmodel import Session, col, delete

from app.common.alchemy import init_connection_engine
from app.db.models import GuildExtensionSettings, WidgetSettings

logger = logging.getLogger(__name__)

# Central registry: extension_name -> event_name -> callback
_hooks: dict[str, dict[str, Callable[..., Any]]] = {}


def register_hook(extension_name: str, event: str, callback: Callable[..., Any]) -> None:
    """Register a lifecycle *callback* for *event* on *extension_name*.

    Only one callback per (extension, event) pair is stored; a second
    registration silently overwrites the first.
    """
    _hooks.setdefault(extension_name, {})[event] = callback
    logger.info("Registered hook '%s' for extension '%s'.", event, extension_name)


def supports_delete_data(extension_name: str) -> bool:
    """Return ``True`` if *extension_name* has a ``delete_guild_data`` hook."""
    return "delete_guild_data" in _hooks.get(extension_name, {})


def get_deletable_extensions() -> list[str]:
    """Return a sorted list of extension names that support data deletion."""
    return sorted(ext for ext, events in _hooks.items() if "delete_guild_data" in events)


def run_hook(extension_name: str, event: str, **kwargs: Any) -> None:
    """Execute the registered hook for (*extension_name*, *event*).

    For ``delete_guild_data`` events the core ``GuildExtensionSettings``
    and ``WidgetSettings`` rows are **always** cleaned up, regardless of
    whether the extension registered a custom callback.

    Raises nothing — errors are logged but swallowed so one bad hook
    cannot break the entire cleanup flow.
    """
    guild_id: int | None = kwargs.get("guild_id")

    # 1. Run the extension's own callback (if any)
    cb = _hooks.get(extension_name, {}).get(event)
    if cb is not None:
        try:
            cb(**kwargs)
            logger.info(
                "Hook '%s' executed for extension '%s' (kwargs=%s).",
                event,
                extension_name,
                kwargs,
            )
        except Exception:
            logger.exception(
                "Hook '%s' failed for extension '%s'.",
                event,
                extension_name,
            )
    else:
        logger.warning(
            "No hook '%s' registered for extension '%s'; skipping.",
            event,
            extension_name,
        )

    # 2. Core cleanup: always wipe Powercord's own per-guild settings
    if event == "delete_guild_data" and guild_id is not None:
        _delete_core_settings(guild_id, extension_name)


def _delete_core_settings(guild_id: int, extension_name: str) -> None:
    """Remove ``GuildExtensionSettings`` and ``WidgetSettings`` rows
    for the given *guild_id* + *extension_name* combination."""
    engine = init_connection_engine()
    try:
        with Session(engine) as session:
            session.exec(
                delete(GuildExtensionSettings).where(
                    col(GuildExtensionSettings.guild_id) == guild_id,
                    col(GuildExtensionSettings.extension_name) == extension_name,
                )
            )
            session.exec(
                delete(WidgetSettings).where(
                    col(WidgetSettings.guild_id) == guild_id,
                    col(WidgetSettings.extension_name) == extension_name,
                )
            )
            session.commit()
        logger.info(
            "Core settings cleaned for extension '%s' on guild %s.",
            extension_name,
            guild_id,
        )
    except Exception:
        logger.exception(
            "Failed to clean core settings for extension '%s' on guild %s.",
            extension_name,
            guild_id,
        )
