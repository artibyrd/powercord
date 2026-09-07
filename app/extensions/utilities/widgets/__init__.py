"""FastHTML dashboard widgets for the utilities extension."""

from app.extensions.utilities.widgets.alerts import guild_admin_alerts_widget
from app.extensions.utilities.widgets.auxiliary import (
    guild_admin_utilities_help_bubble,
    guild_admin_utilities_sidebar,
)
from app.extensions.utilities.widgets.channels import guild_admin_audit_channels_widget
from app.extensions.utilities.widgets.overrides import guild_admin_security_overrides_widget
from app.extensions.utilities.widgets.overview import guild_admin_security_overview_widget
from app.extensions.utilities.widgets.permissions import guild_admin_audit_permissions_widget
from app.extensions.utilities.widgets.roles import guild_admin_audit_roles_widget
from app.extensions.utilities.widgets.settings import guild_admin_auditor_settings_widget

__all__ = [
    "guild_admin_alerts_widget",
    "guild_admin_audit_channels_widget",
    "guild_admin_audit_permissions_widget",
    "guild_admin_audit_roles_widget",
    "guild_admin_auditor_settings_widget",
    "guild_admin_security_overrides_widget",
    "guild_admin_security_overview_widget",
    "guild_admin_utilities_help_bubble",
    "guild_admin_utilities_sidebar",
]
