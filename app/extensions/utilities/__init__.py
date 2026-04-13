from sqlmodel import Session, col, delete

from app.common.alchemy import init_connection_engine
from app.common.extension_hooks import register_hook
from app.db.models import DiscordChannel as DiscordChannel  # Register with SQLModel.metadata
from app.db.models import DiscordRole as DiscordRole


def _delete_guild_data(guild_id: int) -> None:
    """Remove all audit snapshot data for a specific guild."""
    _engine = init_connection_engine()
    with Session(_engine) as session:
        session.exec(delete(DiscordRole).where(col(DiscordRole.guild_id) == guild_id))
        session.exec(delete(DiscordChannel).where(col(DiscordChannel.guild_id) == guild_id))
        session.commit()


register_hook("utilities", "delete_guild_data", _delete_guild_data)
