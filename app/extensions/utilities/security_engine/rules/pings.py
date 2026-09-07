"""Ping and announcement security audit rules."""

import json

from sqlmodel import Session, select

from app.db.models import DiscordAuditorConfig, DiscordChannel, DiscordRole
from app.extensions.utilities.security_engine.calculations import compute_effective_channel_permissions
from app.extensions.utilities.security_engine.constants import decode_permissions
from app.extensions.utilities.security_engine.rules.base import SecurityRule


class PublicAnnouncementProtection(SecurityRule):
    name = "Public Announcement Protection"
    category = "pings"
    severity = "high"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        ann_channel_ids = []
        sep_role_id = None
        if config:
            try:
                ann_channel_ids = json.loads(config.announcement_channel_ids or "[]")
            except Exception:  # noqa: S110
                pass
            sep_role_id = config.staff_separator_role_id

        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        everyone_role = next((r for r in roles if r.position == 0 or r.id == guild_id), None)

        sep_pos = None
        if sep_role_id:
            sep_role = next((r for r in roles if r.id == sep_role_id), None)
            if sep_role:
                sep_pos = sep_role.position

        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
        categories = {c.id: c for c in channels if c.type == "category"}
        alerts = []

        for c in channels:
            if c.type == "category":
                continue
            is_ann = (c.id in ann_channel_ids) or c.type == "news"
            if not is_ann:
                continue

            try:
                overwrites = json.loads(c.overwrites or "{}")
            except Exception:  # noqa: S112
                continue

            # Resolve parent category overwrites for inheritance
            parent_overwrites = None
            parent = categories.get(c.parent_id) if c.parent_id else None
            if parent:
                try:
                    parent_overwrites = json.loads(parent.overwrites or "{}")
                except Exception:  # noqa: S110
                    pass

            for r in roles:
                is_everyone = r.position == 0 or r.id == guild_id
                is_below_sep = sep_pos is not None and r.position < sep_pos
                if is_everyone or is_below_sep:
                    p = compute_effective_channel_permissions(r, c, everyone_role, overwrites, parent_overwrites)
                    # Skip alert if the role can't even see the channel
                    if not (p & (1 << 10)):
                        continue
                    # Check for send messages (1<<11), mention everyone (1<<17), or global Administrator (1<<3)
                    if (p & (1 << 11)) or (p & (1 << 17)) or (r.permissions & (1 << 3)):
                        alerts.append(
                            {
                                "rule": self.name,
                                "category": self.category,
                                "severity": self.severity,
                                "message": f"Announcement channel #{c.name} allows role '{r.name}' to send messages or mention everyone.",
                                "details": f"Role '{r.name}' (position {r.position}) has effective permissions {decode_permissions(p)} in announcement channel.",
                                "action_buttons": [],
                                "role_name": r.name,
                            }
                        )
        return alerts


class UnauthorizedChatPings(SecurityRule):
    name = "Unauthorized Chat Pings in Non-Text Locations"
    category = "pings"
    severity = "medium"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        sep_role_id = config.staff_separator_role_id if config else None

        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        everyone_role = next((r for r in roles if r.position == 0 or r.id == guild_id), None)

        sep_pos = None
        if sep_role_id:
            sep_role = next((r for r in roles if r.id == sep_role_id), None)
            if sep_role:
                sep_pos = sep_role.position

        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
        categories = {c.id: c for c in channels if c.type == "category"}
        alerts = []

        for c in channels:
            if not any(k in c.type.lower() for k in ["voice", "thread", "forum"]):
                continue

            try:
                overwrites = json.loads(c.overwrites or "{}")
            except Exception:  # noqa: S112
                continue

            # Resolve parent category overwrites for inheritance
            parent_overwrites = None
            parent = categories.get(c.parent_id) if c.parent_id else None
            if parent:
                try:
                    parent_overwrites = json.loads(parent.overwrites or "{}")
                except Exception:  # noqa: S110
                    pass

            for r in roles:
                is_everyone = r.position == 0 or r.id == guild_id
                is_below_sep = sep_pos is not None and r.position < sep_pos
                if is_everyone or is_below_sep:
                    p = compute_effective_channel_permissions(r, c, everyone_role, overwrites, parent_overwrites)
                    # Skip alert if the role can't even see the channel
                    if not (p & (1 << 10)):
                        continue
                    if (p & (1 << 11)) or (p & (1 << 17)) or (r.permissions & (1 << 3)):
                        alerts.append(
                            {
                                "rule": self.name,
                                "category": self.category,
                                "severity": self.severity,
                                "message": f"Non-text location #{c.name} allows role '{r.name}' to send messages or mention everyone.",
                                "details": f"Channel of type '{c.type}' allows non-admin role '{r.name}' to Send Messages or Mention Everyone. Allowed permissions: {decode_permissions(p)}.",
                                "action_buttons": [],
                                "role_name": r.name,
                            }
                        )
        return alerts


class GeneralRoleMentionability(SecurityRule):
    name = "General Role Mentionability"
    category = "pings"
    severity = "low"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        sep_role_id = config.staff_separator_role_id if config else None
        if not sep_role_id:
            return []

        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        sep_role = next((r for r in roles if r.id == sep_role_id), None)
        if not sep_role:
            return []

        sep_pos = sep_role.position
        alerts = []

        for r in roles:
            if r.position < sep_pos and not r.is_managed and r.is_mentionable:
                alerts.append(
                    {
                        "rule": self.name,
                        "category": self.category,
                        "severity": self.severity,
                        "message": f"Low-tier role '{r.name}' is mentionable.",
                        "details": f"Role '{r.name}' is a non-admin role set to mentionable, posing a mass ping raid vulnerability.",
                        "action_buttons": [],
                        "role_name": r.name,
                    }
                )
        return alerts
