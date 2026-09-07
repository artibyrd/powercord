"""Constants and decoding helpers for Discord permissions and security risk categories."""

from app.common.discord_constants import ALL_PERMISSIONS

high_risk_perms: set[str] = {
    "Administrator",
    "Manage Server",
    "Manage Roles",
    "Manage Channels",
    "Kick Members",
    "Ban Members",
    "Manage Messages",
    "Mention Everyone",
    "Moderate Members",
    "Manage Webhooks",
}

medium_risk_perms: set[str] = {
    "View Audit Log",
    "Mute Members",
    "Deafen Members",
    "Move Members",
    "Manage Emojis & Stickers",
    "Manage Events",
    "View Channel",
    "Send Messages",
    "Send Messages in Threads",
    "Create Public Threads",
    "Create Private Threads",
    "Manage Nicknames",
}


def decode_permissions(perms_int: int) -> str:
    """Decodes any permission bitmask into a comma-separated string of single-quoted,
    human-readable permission names based on ALL_PERMISSIONS.
    If no permissions are active, returns 'none'.
    """
    active = []
    for name, value in ALL_PERMISSIONS.items():
        if (perms_int & value) == value:
            active.append(f"'{name}'")
    if not active:
        return "none"
    return ", ".join(active)
