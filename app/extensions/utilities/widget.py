# mypy: ignore-errors
"""Utilities extension FastHTML widgets and security auditor facade."""

import hashlib
from typing import Optional

from sqlmodel import Session

from app.common.alchemy import init_connection_engine
from app.extensions.utilities.security_engine import (
    SECURITY_RULES,
    CategoryPermissionBaseline,
    EvaluationCache,
    ExposedStaffChannels,
    GeneralRoleMentionability,
    LowTierRolePrivileges,
    OverPrivilegedBotIntegrations,
    PublicAnnouncementProtection,
    SecurityRule,
    SecurityRuleEngine,
    SuggestiveHoneypotIntegration,
    UnauthorizedChatPings,
    compute_effective_channel_permissions,
    decode_permissions,
    get_effective_channel_permissions,
    high_risk_perms,
    medium_risk_perms,
)
from app.extensions.utilities.views import (
    _render_alerts_list,
    format_details,
    format_message,
    get_override_confirm_modal_html,
    get_security_rules_modal,
)
from app.extensions.utilities.widgets import (
    guild_admin_alerts_widget as _alerts_widget,
)
from app.extensions.utilities.widgets import (
    guild_admin_audit_channels_widget as _audit_channels_widget,
)
from app.extensions.utilities.widgets import (
    guild_admin_audit_permissions_widget as _audit_permissions_widget,
)
from app.extensions.utilities.widgets import (
    guild_admin_audit_roles_widget as _audit_roles_widget,
)
from app.extensions.utilities.widgets import (
    guild_admin_auditor_settings_widget as _auditor_settings_widget,
)
from app.extensions.utilities.widgets import (
    guild_admin_security_overrides_widget as _security_overrides_widget,
)
from app.extensions.utilities.widgets import (
    guild_admin_security_overview_widget as _security_overview_widget,
)
from app.extensions.utilities.widgets import (
    guild_admin_utilities_help_bubble as _utilities_help_bubble,
)
from app.extensions.utilities.widgets import (
    guild_admin_utilities_sidebar as _utilities_sidebar,
)

engine = init_connection_engine()


# ── Dashboard Widget Pass-throughs (Module-bound for Gadget Discovery) ─────────


def guild_admin_security_overview_widget(guild_id: int):
    """Provides a high-level summary of the server's security posture."""
    return _security_overview_widget(guild_id)


def guild_admin_alerts_widget(guild_id: int, category: str = "all"):
    """Renders the list of security alerts filterable by a TabGroup tab bar."""
    return _alerts_widget(guild_id, category=category)


def guild_admin_auditor_settings_widget(guild_id: int):
    """Renders the settings card for managing auditor configurations."""
    return _auditor_settings_widget(guild_id)


def guild_admin_audit_roles_widget(guild_id: int):
    """Displays Discord server roles for a specific guild."""
    return _audit_roles_widget(guild_id)


def guild_admin_audit_channels_widget(guild_id: int):
    """Displays Discord server channels for a specific guild."""
    return _audit_channels_widget(guild_id)


def guild_admin_audit_permissions_widget(guild_id: int):
    """Displays a matrix correlating permissions to roles."""
    return _audit_permissions_widget(guild_id)


def guild_admin_security_overrides_widget(guild_id: int):
    """Displays overridden security alerts with option to remove override."""
    return _security_overrides_widget(guild_id)


def guild_admin_utilities_sidebar(guild_id: int, session: Optional[Session] = None):
    """Dashboard sidebar navigation and health status widget."""
    return _utilities_sidebar(guild_id, session=session)


guild_admin_utilities_sidebar.position_config = "left"


def guild_admin_utilities_help_bubble(guild_id: int, session: Optional[Session] = None):
    """Floating help bubble widget providing slash command cheatsheet and connection ping."""
    return _utilities_help_bubble(guild_id, session=session)


guild_admin_utilities_help_bubble.position_config = "bottom-right"


# ── Public Re-exports for Backward Compatibility ───────────────────────────────

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
    "Session",
    "SuggestiveHoneypotIntegration",
    "UnauthorizedChatPings",
    "_render_alerts_list",
    "compute_effective_channel_permissions",
    "decode_permissions",
    "engine",
    "format_details",
    "format_message",
    "get_effective_channel_permissions",
    "get_override_confirm_modal_html",
    "get_security_rules_modal",
    "guild_admin_alerts_widget",
    "guild_admin_audit_channels_widget",
    "guild_admin_audit_permissions_widget",
    "guild_admin_audit_roles_widget",
    "guild_admin_auditor_settings_widget",
    "guild_admin_security_overrides_widget",
    "guild_admin_security_overview_widget",
    "guild_admin_utilities_help_bubble",
    "guild_admin_utilities_sidebar",
    "hashlib",
    "high_risk_perms",
    "medium_risk_perms",
]
