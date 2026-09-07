"""Security auditor engine subpackage."""

from app.extensions.utilities.security_engine.calculations import (
    compute_alert_hash,
    compute_db_checksum,
    compute_effective_channel_permissions,
    compute_security_health_score,
    get_effective_channel_permissions,
)
from app.extensions.utilities.security_engine.constants import (
    decode_permissions,
    high_risk_perms,
    medium_risk_perms,
)
from app.extensions.utilities.security_engine.engine import (
    EvaluationCache,
    SecurityRuleEngine,
)
from app.extensions.utilities.security_engine.rules import (
    SECURITY_RULES,
    CategoryPermissionBaseline,
    ExposedStaffChannels,
    GeneralRoleMentionability,
    LowTierRolePrivileges,
    OverPrivilegedBotIntegrations,
    PublicAnnouncementProtection,
    SecurityRule,
    SuggestiveHoneypotIntegration,
    UnauthorizedChatPings,
)

__all__ = [
    "SECURITY_RULES",
    "CategoryPermissionBaseline",
    "EvaluationCache",
    "ExposedStaffChannels",
    "GeneralRoleMentionability",
    "LowTierRolePrivileges",
    "OverPrivilegedBotIntegrations",
    "PublicAnnouncementProtection",
    "SecurityRule",
    "SecurityRuleEngine",
    "SuggestiveHoneypotIntegration",
    "UnauthorizedChatPings",
    "compute_alert_hash",
    "compute_db_checksum",
    "compute_effective_channel_permissions",
    "compute_security_health_score",
    "decode_permissions",
    "get_effective_channel_permissions",
    "high_risk_perms",
    "medium_risk_perms",
]
