"""Security auditor rule definitions and registry."""

from app.extensions.utilities.security_engine.rules.base import SecurityRule
from app.extensions.utilities.security_engine.rules.exposure import (
    CategoryPermissionBaseline,
    ExposedStaffChannels,
)
from app.extensions.utilities.security_engine.rules.integrations import (
    SuggestiveHoneypotIntegration,
)
from app.extensions.utilities.security_engine.rules.pings import (
    GeneralRoleMentionability,
    PublicAnnouncementProtection,
    UnauthorizedChatPings,
)
from app.extensions.utilities.security_engine.rules.roles import (
    LowTierRolePrivileges,
    OverPrivilegedBotIntegrations,
)

SECURITY_RULES: list[type[SecurityRule]] = [
    CategoryPermissionBaseline,
    PublicAnnouncementProtection,
    ExposedStaffChannels,
    UnauthorizedChatPings,
    LowTierRolePrivileges,
    GeneralRoleMentionability,
    SuggestiveHoneypotIntegration,
    OverPrivilegedBotIntegrations,
]

__all__ = [
    "SECURITY_RULES",
    "CategoryPermissionBaseline",
    "ExposedStaffChannels",
    "GeneralRoleMentionability",
    "LowTierRolePrivileges",
    "OverPrivilegedBotIntegrations",
    "PublicAnnouncementProtection",
    "SecurityRule",
    "SuggestiveHoneypotIntegration",
    "UnauthorizedChatPings",
]
