"""
Shared constants for Discord API related values.
"""

SENSITIVE_PERMISSIONS = {
    "Administrator": 1 << 3,
    "Manage Server": 1 << 5,
    "Manage Roles": 1 << 28,
    "Manage Channels": 1 << 4,
    "Kick Members": 1 << 1,
    "Ban Members": 1 << 2,
    "Manage Messages": 1 << 13,
    "Mention Everyone": 1 << 17,
}

OTHER_PERMISSIONS = {
    "Create Instant Invite": 1 << 0,
    "Add Reactions": 1 << 6,
    "View Audit Log": 1 << 7,
    "Priority Speaker": 1 << 8,
    "Stream": 1 << 9,
    "View Channel": 1 << 10,
    "Send Messages": 1 << 11,
    "Send TTS Messages": 1 << 12,
    "Embed Links": 1 << 14,
    "Attach Files": 1 << 15,
    "Read Message History": 1 << 16,
    "Use External Emojis": 1 << 18,
    "View Guild Insights": 1 << 19,
    "Connect": 1 << 20,
    "Speak": 1 << 21,
    "Mute Members": 1 << 22,
    "Deafen Members": 1 << 23,
    "Move Members": 1 << 24,
    "Use VAD": 1 << 25,
    "Change Nickname": 1 << 26,
    "Manage Nicknames": 1 << 27,
    "Manage Webhooks": 1 << 29,
    "Manage Emojis & Stickers": 1 << 30,
    "Use Slash Commands": 1 << 31,
    "Request to Speak": 1 << 32,
    "Manage Events": 1 << 33,
    "Manage Threads": 1 << 34,
    "Create Public Threads": 1 << 35,
    "Create Private Threads": 1 << 36,
    "Use External Stickers": 1 << 37,
    "Send Messages in Threads": 1 << 38,
    "Use Embedded Activities": 1 << 39,
    "Moderate Members": 1 << 40,
}

ALL_PERMISSIONS = {**SENSITIVE_PERMISSIONS, **OTHER_PERMISSIONS}
