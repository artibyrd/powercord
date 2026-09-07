"""Exposure-related security audit rules."""

import json

from sqlmodel import Session, select

from app.db.models import DiscordAuditorConfig, DiscordChannel, DiscordRole
from app.extensions.utilities.security_engine.calculations import compute_effective_channel_permissions
from app.extensions.utilities.security_engine.constants import decode_permissions
from app.extensions.utilities.security_engine.rules.base import SecurityRule


class CategoryPermissionBaseline(SecurityRule):
    name = "Category Permission Baseline"
    category = "exposure"
    severity = "medium"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
        categories = {c.id: c for c in channels if c.type == "category"}
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        role_map = {str(r.id): r.name for r in roles}
        alerts: list[dict] = []

        for child in channels:
            if child.type == "category" or not child.parent_id:
                continue
            parent = categories.get(child.parent_id)
            if not parent:
                continue

            try:
                child_ov = json.loads(child.overwrites or "{}")
                parent_ov = json.loads(parent.overwrites or "{}")
            except Exception:  # noqa: S112
                continue

            # Only iterate child keys; targets absent from child inherit parent's baseline (no leak)
            for target_id in child_ov.keys():
                c_target = child_ov.get(target_id, {})
                p_target = parent_ov.get(target_id, {})

                c_allow = c_target.get("allow", 0)
                c_deny = c_target.get("deny", 0)
                p_allow = p_target.get("allow", 0)
                p_deny = p_target.get("deny", 0)

                leaked_allows = c_allow & ~p_allow
                leaked_denies = p_deny & ~c_deny

                if leaked_allows or leaked_denies:
                    is_view_leak = bool((leaked_allows & (1 << 10)) or (leaked_denies & (1 << 10)))
                    alert_severity = "high" if is_view_leak else self.severity

                    # Check if this leak is inert because View Channel is effectively denied
                    view_channel_bit = 1 << 10
                    target_has_view = False
                    if c_allow & view_channel_bit:
                        target_has_view = True
                    elif not (c_deny & view_channel_bit):
                        # Not denied at child level — check parent
                        if not (p_deny & view_channel_bit):
                            target_has_view = True

                    is_inert = not target_has_view and not is_view_leak
                    if is_inert:
                        alert_severity = "low"
                        inert_label = " [INERT — View Channel denied; this leak has no practical effect]"
                    else:
                        inert_label = ""

                    target_meta = child_ov.get(target_id, {})
                    t_type = target_meta.get("type")
                    t_name = target_meta.get("name")

                    role_name = None
                    if target_id in role_map:
                        display_name = f"Role '{role_map[target_id]}'"
                        role_name = role_map[target_id]
                    elif t_name:
                        if t_type == "role":
                            display_name = f"Role '{t_name}'"
                            role_name = t_name
                        elif t_type == "member":
                            display_name = f"Member '{t_name}'"
                        else:
                            display_name = f"ID '{t_name}'"
                    else:
                        if t_type == "role":
                            display_name = f"Role ID {target_id}"
                        elif t_type == "member":
                            display_name = f"Member ID {target_id}"
                        else:
                            display_name = f"ID {target_id}"

                    alerts.append(
                        {
                            "rule": self.name,
                            "category": self.category,
                            "severity": alert_severity,
                            "message": f"Channel #{child.name} has permission exposure leak compared to parent category {parent.name}.",
                            "details": f"Target {display_name} has less restricted overwrites. Leaked allows: {decode_permissions(leaked_allows)}, leaked denies: {decode_permissions(leaked_denies)}.{inert_label}",
                            "action_buttons": [],
                            "role_name": role_name,
                        }
                    )
        return alerts


class ExposedStaffChannels(SecurityRule):
    name = "Exposed Staff Channels"
    category = "exposure"
    severity = "high"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        staff_channel_ids = []
        sep_role_id = None
        if config:
            try:
                staff_channel_ids = json.loads(config.staff_channel_ids or "[]")
            except Exception:  # noqa: S110
                pass
            sep_role_id = config.staff_separator_role_id

        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        everyone_role = next((r for r in roles if r.position == 0 or r.id == guild_id), None)
        if not everyone_role:
            everyone_role = DiscordRole(id=guild_id, guild_id=guild_id, name="@everyone", permissions=0, position=0)
            roles = [everyone_role] + list(roles)

        sep_pos = None
        if sep_role_id:
            sep_role = next((r for r in roles if r.id == sep_role_id), None)
            if sep_role:
                sep_pos = sep_role.position

        # Determine non-staff roles
        non_staff_roles = []
        for r in roles:
            is_everyone = r.position == 0 or r.id == guild_id
            is_below_sep = sep_pos is not None and r.position < sep_pos
            if is_everyone or is_below_sep:
                non_staff_roles.append(r)

        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
        categories = {c.id: c for c in channels if c.type == "category"}
        alerts = []

        for c in channels:
            if c.type == "category":
                continue
            is_staff = c.id in staff_channel_ids
            if not is_staff:
                continue

            try:
                overwrites = json.loads(c.overwrites or "{}")
            except Exception:
                overwrites = {}

            # Resolve parent category overwrites for inheritance
            parent_overwrites = None
            parent = categories.get(c.parent_id) if c.parent_id else None
            if parent:
                try:
                    parent_overwrites = json.loads(parent.overwrites or "{}")
                except Exception:  # noqa: S110
                    pass

            for r in non_staff_roles:
                p = compute_effective_channel_permissions(r, c, everyone_role, overwrites, parent_overwrites)
                has_view = bool(p & (1 << 10))

                if has_view:
                    alerts.append(
                        {
                            "rule": self.name,
                            "category": self.category,
                            "severity": self.severity,
                            "message": f"Staff channel #{c.name} is visible to {r.name}.",
                            "details": f"Role '{r.name}' (position {r.position}) has View Channel (1 << 10) permission in staff channel.",
                            "action_buttons": [],
                            "role_name": r.name,
                        }
                    )
        return alerts
