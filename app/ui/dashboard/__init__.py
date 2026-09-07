# mypy: ignore-errors
from __future__ import annotations

from fasthtml.core import APIRouter

# Re-export helper functions frequently patched in tests on app.ui.dashboard
from app.common.extension_loader import GadgetInspector
from app.common.extension_manager import get_installed_extensions
from app.ui.dashboard.api_keys import (
    _render_self_service_keys,
    generate_guild_api_key_route,
    revoke_guild_api_key_route,
)
from app.ui.dashboard.grid import (
    _get_ordered_widgets,
    _humanize_widget_name,
    format_extension_title,
    server_extension_card,
)
from app.ui.dashboard.layout import (
    _render_layout_editor,
    admin_layout_editor,
    guild_layout_editor,
    layout_editor,
    layout_move,
    layout_restore,
    layout_router,
    layout_update,
)
from app.ui.dashboard.placement import (
    VALID_FIXED_POSITIONS,
    VALID_FLOATING_POSITIONS,
    check_position_collisions,
    classify_widget_placement,
    normalize_position_config,
)
from app.ui.dashboard.roles import (
    _check_guild_admin,
    _get_guild_roles,
    _render_access_roles,
    _render_api_user_role,
    add_access_role,
    remove_access_role,
    remove_api_role,
    set_api_role,
)
from app.ui.dashboard.settings import (
    post_alert_override,
    post_alert_override_remove,
    post_auditor_settings,
    settings_router,
    toggle_nav_route,
)
from app.ui.helpers import (
    get_admin_guilds,
    get_guild_cogs,
    get_guild_sprockets,
    get_guild_widgets,
    get_internal_api_client,
    get_widget_name,
    get_widget_settings,
    is_dashboard_admin,
    is_gadget_enabled,
    update_guild_extension_setting,
    update_widget_setting,
)
from app.ui.routes.guild import (
    confirm_delete_data_route,
    dashboard,
    dashboard_ping_bot,
    dashboard_scan_guild,
    delete_server_data_route,
    get_alerts_list,
    get_override_confirm_modal,
    get_rules_info,
    guild_router,
    lockdown_route,
    server_extension_details_route,
    toggle_server_extension,
)

# Unified dashboard router combining layout, settings, and guild routes
dashboard_router = APIRouter()
dashboard_router.routes.extend(layout_router.routes)
dashboard_router.routes.extend(settings_router.routes)
dashboard_router.routes.extend(guild_router.routes)

__all__ = [
    "dashboard_router",
    "dashboard",
    "lockdown_route",
    "toggle_nav_route",
    "layout_editor",
    "admin_layout_editor",
    "guild_layout_editor",
    "layout_update",
    "layout_move",
    "layout_restore",
    "_render_layout_editor",
    "_get_ordered_widgets",
    "_humanize_widget_name",
    "format_extension_title",
    "server_extension_card",
    "VALID_FIXED_POSITIONS",
    "VALID_FLOATING_POSITIONS",
    "normalize_position_config",
    "classify_widget_placement",
    "check_position_collisions",
    "_check_guild_admin",
    "_get_guild_roles",
    "_render_access_roles",
    "add_access_role",
    "remove_access_role",
    "_render_api_user_role",
    "set_api_role",
    "remove_api_role",
    "_render_self_service_keys",
    "generate_guild_api_key_route",
    "revoke_guild_api_key_route",
    "post_auditor_settings",
    "post_alert_override",
    "post_alert_override_remove",
    "server_extension_details_route",
    "confirm_delete_data_route",
    "delete_server_data_route",
    "toggle_server_extension",
    "dashboard_scan_guild",
    "dashboard_ping_bot",
    "get_alerts_list",
    "get_rules_info",
    "get_override_confirm_modal",
    "get_widget_settings",
    "is_gadget_enabled",
    "GadgetInspector",
    "update_widget_setting",
    "update_guild_extension_setting",
    "get_admin_guilds",
    "get_internal_api_client",
    "get_guild_cogs",
    "get_guild_sprockets",
    "get_guild_widgets",
    "get_widget_name",
    "is_dashboard_admin",
    "get_installed_extensions",
]
