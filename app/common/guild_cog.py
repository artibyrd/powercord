"""Base cog class that respects per-guild extension toggle settings.

Cogs that inherit from ``GuildAwareCog`` will automatically:
- Gate **prefix commands** via ``cog_check(ctx)``
- Gate **slash / application commands** via ``interaction_check(interaction)``
- Expose ``guild_enabled(guild_id)`` for manual listener guards

The extension name is derived from the cog's module path
(``app.extensions.<name>.cog``), so no configuration is needed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from nextcord.ext import commands

if TYPE_CHECKING:
    import nextcord

logger = logging.getLogger(__name__)


class GuildAwareCog(commands.Cog):
    """Cog base class that checks per-guild enabled state.

    Subclasses get automatic command gating.  For listeners, call
    ``self.guild_enabled(guild_id)`` at the top of each handler
    and return early when it is ``False``.
    """

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        # Derive extension name from module path: app.extensions.<name>.cog
        parts = type(self).__module__.split(".")
        try:
            ext_idx = parts.index("extensions")
            self._extension_name: str = parts[ext_idx + 1]
        except (ValueError, IndexError):
            # Fallback: use the cog's qualified name in lowercase
            self._extension_name = type(self).__name__.lower()
            logger.warning(
                "Could not derive extension name from module path for %s; "
                "using '%s'.  Per-guild gating may not work correctly.",
                type(self).__name__,
                self._extension_name,
            )

    # ------------------------------------------------------------------
    # Public helper – call from listeners
    # ------------------------------------------------------------------

    def guild_enabled(self, guild_id: int | None) -> bool:
        """Return ``True`` if this cog is enabled for *guild_id*.

        Returns ``True`` for DMs (``guild_id is None``) so direct-message
        commands are not accidentally blocked.
        """
        if guild_id is None:
            return True  # DMs are always allowed

        # Lazy import to avoid circular dependency with the UI layer
        from app.ui.helpers import is_gadget_enabled

        return is_gadget_enabled(guild_id, self._extension_name, "cog")

    # ------------------------------------------------------------------
    # Automatic command gates
    # ------------------------------------------------------------------

    async def cog_check(self, ctx: commands.Context) -> bool:  # type: ignore[override]
        """Gate all prefix commands in this cog by guild enabled state."""
        guild_id = ctx.guild.id if ctx.guild else None
        return self.guild_enabled(guild_id)

    async def interaction_check(self, interaction: nextcord.Interaction) -> bool:
        """Gate all slash / application commands in this cog by guild enabled state."""
        guild_id = interaction.guild_id
        return self.guild_enabled(guild_id)
