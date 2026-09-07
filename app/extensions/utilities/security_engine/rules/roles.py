"""Role-based security audit rules."""

from sqlmodel import Session, select

from app.db.models import DiscordAuditorConfig, DiscordRole
from app.extensions.utilities.security_engine.constants import decode_permissions
from app.extensions.utilities.security_engine.rules.base import SecurityRule


class LowTierRolePrivileges(SecurityRule):
    name = "Low-Tier Role Privileges"
    category = "roles"
    severity = "high"

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
        mask = (1 << 3) | (1 << 5) | (1 << 28) | (1 << 4) | (1 << 1) | (1 << 2) | (1 << 17)

        for r in roles:
            if r.position < sep_pos and (r.permissions & mask) != 0:
                alerts.append(
                    {
                        "rule": self.name,
                        "category": self.category,
                        "severity": self.severity,
                        "message": f"Low-tier role '{r.name}' has sensitive permissions.",
                        "details": f"Role '{r.name}' (position {r.position}) has sensitive permissions: {decode_permissions(r.permissions & mask)}.",
                        "action_buttons": [],
                        "role_name": r.name,
                    }
                )
        return alerts


class OverPrivilegedBotIntegrations(SecurityRule):
    name = "Over-privileged Bot Integrations"
    category = "integrations"
    severity = "medium"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        alerts = []
        mask = (1 << 3) | (1 << 5) | (1 << 28) | (1 << 4)

        for r in roles:
            if r.is_managed and (r.permissions & mask) != 0:
                alerts.append(
                    {
                        "rule": self.name,
                        "category": self.category,
                        "severity": self.severity,
                        "message": f"Bot role '{r.name}' has excessive privileges.",
                        "details": f"Managed integration role '{r.name}' has sensitive permissions: {decode_permissions(r.permissions & mask)}.",
                        "action_buttons": [],
                        "role_name": r.name,
                    }
                )
        return alerts
