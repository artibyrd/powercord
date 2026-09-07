"""Integration-related security audit rules."""

import json

from sqlmodel import Session, select

from app.db.models import DiscordChannel, GuildExtensionSettings
from app.extensions.utilities.security_engine.rules.base import SecurityRule


class SuggestiveHoneypotIntegration(SecurityRule):
    name = "Suggestive Honeypot Integration"
    category = "integrations"
    severity = "medium"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        ext_setting = session.exec(
            select(GuildExtensionSettings).where(
                GuildExtensionSettings.guild_id == guild_id,
                GuildExtensionSettings.extension_name == "honeypot",
                GuildExtensionSettings.is_enabled,
            )
        ).first()

        if not ext_setting:
            return [
                {
                    "rule": self.name,
                    "category": self.category,
                    "severity": "low",
                    "message": "Install the honeypot extension to protect public discovery channels.",
                    "details": "The honeypot extension is not currently enabled for this guild. Enabling it adds defensive decoy channels.",
                    "action_buttons": [],
                }
            ]

        try:
            from app.extensions.honeypot.blueprint import HoneypotChannel
        except ImportError:
            HoneypotChannel = None  # type: ignore[assignment, misc]

        protected_ids = set()
        if HoneypotChannel is not None:
            try:
                from sqlalchemy import inspect

                bind = session.get_bind()
                if inspect(bind).has_table("honeypot_channels"):
                    protected_ids = set(
                        session.exec(
                            select(HoneypotChannel.channel_id).where(HoneypotChannel.guild_id == guild_id)
                        ).all()
                    )
            except Exception:  # noqa: S110
                session.rollback()

        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
        alerts = []

        for c in channels:
            if "discovery" not in c.name.lower() or c.type == "category":
                continue

            try:
                overwrites = json.loads(c.overwrites or "{}")
            except Exception:
                overwrites = {}

            everyone_ov = overwrites.get(str(guild_id), {})
            deny_val = everyone_ov.get("deny", 0)
            is_public = (deny_val & (1 << 10)) == 0

            if is_public and c.id not in protected_ids:
                alerts.append(
                    {
                        "rule": self.name,
                        "category": self.category,
                        "severity": self.severity,
                        "message": f"Public discovery channel #{c.name} is unprotected.",
                        "details": f"Channel '{c.name}' is visible to the public but has no honeypot protection configured.",
                        "action_buttons": [
                            {
                                "text": "Protect",
                                "hx_post": f"/api/guild/{guild_id}/audit/honeypot/protect?channel_id={c.id}",
                            },
                            {
                                "text": "Remind Later",
                                "hx_post": f"/api/guild/{guild_id}/audit/honeypot/remind?channel_id={c.id}",
                            },
                            {
                                "text": "No Thanks",
                                "hx_post": f"/api/guild/{guild_id}/audit/honeypot/dismiss?channel_id={c.id}",
                            },
                        ],
                    }
                )
        return alerts
