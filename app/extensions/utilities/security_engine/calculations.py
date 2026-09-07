"""Pure calculation functions for Discord permissions and security health scores."""

import hashlib
import json
import math
from collections.abc import Sequence
from typing import Optional

from app.db.models import DiscordAuditorConfig, DiscordChannel, DiscordRole, SecurityAlertOverride


def compute_effective_channel_permissions(
    role: DiscordRole,
    channel: DiscordChannel,
    everyone_role: Optional[DiscordRole],
    overwrites: dict,
    parent_overwrites: Optional[dict] = None,
) -> int:
    """Calculates effective permissions for a role in a given channel,
    taking into account category inheritance, base permissions, and administrator bypass.
    """
    # Merge parent category overwrites as base layer; channel entries take full precedence per target
    effective_ow = dict(parent_overwrites) if parent_overwrites else {}
    effective_ow.update(overwrites)

    base_everyone = everyone_role.permissions if everyone_role else 0
    if role.position == 0 or (everyone_role and role.id == everyone_role.id):
        ev_ov = effective_ow.get(str(role.id), {})
        allow_ev = ev_ov.get("allow", 0)
        deny_ev = ev_ov.get("deny", 0)
        p = (base_everyone & ~deny_ev) | allow_ev
        if p & (1 << 3):  # Administrator
            return 0xFFFFFFFFFFFFFFFF
        return int(p)

    base_role = role.permissions | base_everyone
    ev_id = str(everyone_role.id) if everyone_role else str(role.guild_id)
    ev_ov = effective_ow.get(ev_id, {})
    allow_ev = ev_ov.get("allow", 0)
    deny_ev = ev_ov.get("deny", 0)

    p = (base_role & ~deny_ev) | allow_ev

    role_ov = effective_ow.get(str(role.id), {})
    allow_r = role_ov.get("allow", 0)
    deny_r = role_ov.get("deny", 0)

    p = (p & ~deny_r) | allow_r

    if (role.permissions & (1 << 3)) or (base_everyone & (1 << 3)) or (p & (1 << 3)):
        return 0xFFFFFFFFFFFFFFFF
    return int(p)


# Backward-compatible alias for existing callers
get_effective_channel_permissions = compute_effective_channel_permissions


def compute_alert_hash(rule: str, category: str, message: str) -> str:
    """Calculates deterministic SHA-256 hash for an alert."""
    raw = f"{rule}:{category}:{message}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_security_health_score(num_high: int, num_medium: int, num_low: int) -> int:
    """Calculates security health score (0-100) using logarithmic diminishing returns."""
    high_penalty = 15 * math.log2(num_high + 1)
    medium_penalty = 10 * math.log2(num_medium + 1)
    low_penalty = 5 * math.log2(num_low + 1)
    score = 100 - (high_penalty + medium_penalty + low_penalty)
    return max(0, min(100, int(round(score))))


def compute_db_checksum(
    roles: Sequence[DiscordRole],
    channels: Sequence[DiscordChannel],
    configs: Sequence[DiscordAuditorConfig],
    overrides: Sequence[SecurityAlertOverride],
) -> str:
    """Calculates a deterministic SHA-256 checksum across Discord role, channel, and config states."""
    roles_sorted = sorted(roles, key=lambda r: r.id or 0)
    roles_serialized = [
        {
            "id": r.id,
            "guild_id": r.guild_id,
            "name": r.name,
            "permissions": r.permissions,
            "position": r.position,
            "color": r.color,
            "is_hoisted": r.is_hoisted,
            "is_managed": r.is_managed,
            "is_mentionable": r.is_mentionable,
        }
        for r in roles_sorted
    ]

    channels_sorted = sorted(channels, key=lambda c: c.id or 0)
    channels_serialized = [
        {
            "id": c.id,
            "guild_id": c.guild_id,
            "parent_id": c.parent_id,
            "name": c.name,
            "type": c.type,
            "position": c.position,
            "overwrites": c.overwrites,
        }
        for c in channels_sorted
    ]

    configs_sorted = sorted(configs, key=lambda c: c.guild_id or 0)
    configs_serialized = [
        {
            "guild_id": c.guild_id,
            "staff_separator_role_id": c.staff_separator_role_id,
            "staff_channel_ids": c.staff_channel_ids,
            "announcement_channel_ids": c.announcement_channel_ids,
        }
        for c in configs_sorted
    ]

    overrides_sorted = sorted(overrides, key=lambda o: o.id or 0)
    overrides_serialized = [
        {
            "alert_hash": o.alert_hash,
            "comment": o.comment,
        }
        for o in overrides_sorted
    ]

    payload = {
        "roles": roles_serialized,
        "channels": channels_serialized,
        "configs": configs_serialized,
        "overrides": overrides_serialized,
    }

    json_str = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
