# mypy: ignore-errors
import hashlib
import json
import logging
import re
from typing import Optional

from cachetools import TTLCache
from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.common.discord_constants import ALL_PERMISSIONS, OTHER_PERMISSIONS, SENSITIVE_PERMISSIONS
from app.db.models import (
    DiscordAuditorConfig,
    DiscordChannel,
    DiscordRole,
    GuildExtensionSettings,
    SecurityAlertOverride,
)
from app.ui.components import (
    Accordion,
    Card,
    HealthScoreArc,
    ProgressBarStat,
    SegmentedDigit,
    TabGroup,
)

engine = init_connection_engine()


high_risk_perms = {
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

medium_risk_perms = {
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


def _get_common_legend(for_roles=False):
    items = []
    if for_roles:
        items.append(
            Li(
                Span("✅: ", cls="font-bold"),
                "Indicates if a role is Sidebar (displayed separately) or Bot/Int (managed by an integration).",
            )
        )
        items.append(
            Li(
                Span("Key Perms: ", cls="font-bold"),
                Span("Admin", cls="badge badge-error badge-sm px-2 rounded-md mr-1"),
                "= Administrator, ",
                Span("Manager", cls="badge badge-warning badge-sm px-2 rounded-md mr-1"),
                "= Manage Server/Roles/Channels, ",
                Span("Mod", cls="badge badge-info badge-sm px-2 rounded-md mr-1"),
                "= Kick/Ban Members.",
            )
        )
    else:
        items.append(
            Li(
                Span("Badges: ", cls="font-bold"),
                Span("Green", cls="badge badge-success badge-sm px-2 rounded-md mr-1"),
                "= Explicit Allow, ",
                Span("Red", cls="badge badge-error badge-sm px-2 rounded-md mr-1"),
                "= Explicit Deny.",
            )
        )
        items.append(Li(Span("Icons: ", cls="font-bold"), "📢=Text, 🔊=Voice, 🏛️=Forum, 📁=Category"))

    items.append(
        Li(
            Span("Note: ", cls="font-bold"),
            "Permissions shown are explicit overrides. Inherited permissions are not listed.",
        )
    )

    return Div(
        H4("Legend:", cls="font-bold text-sm mb-2 opacity-70"),
        Ul(*items, cls="list-disc list-inside text-xs opacity-70"),
        cls="bg-base-200/50 p-3 rounded-md mb-4",
    )


def _get_role_badges(permissions: int) -> list[FT]:
    """Decodes discord permissions and returns a list of FastHTML badges."""
    badges = []

    # Administrator
    if permissions & (1 << 3):
        badges.append(
            Span(
                "Admin",
                cls="badge badge-error badge-sm px-2 py-0.5 rounded-md mr-1 mb-1 font-bold",
                title="Administrator",
            )
        )

    # Manager (Manage Server, Manage Roles, Manage Channels)
    if permissions & (1 << 5) or permissions & (1 << 28) or permissions & (1 << 4):
        badges.append(
            Span(
                "Manager",
                cls="badge badge-warning badge-sm px-2 py-0.5 rounded-md mr-1 mb-1",
                title="Manage Server/Roles/Channels",
            )
        )

    # Moderator (Kick, Ban)
    if permissions & (1 << 1) or permissions & (1 << 2):
        badges.append(
            Span("Mod", cls="badge badge-info badge-sm px-2 py-0.5 rounded-md mr-1 mb-1", title="Kick/Ban Members")
        )

    return badges


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


def guild_admin_audit_roles_widget(guild_id: int):
    """Displays Discord server roles for a specific guild.

    Fetches the roles stored by the `utilities` audit command and renders them
    in a detailed FastHTML table with color indicators and permission badges.
    """
    with Session(engine) as session:
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()

    if not roles:
        return Accordion(
            "Guild Roles",
            Div("No roles found for this server.", cls="opacity-70 text-sm mt-2"),
            open=False,
            id=f"guild-admin-audit-roles-{guild_id}",
        )

    roles = sorted(roles, key=lambda x: x.position, reverse=True)

    role_rows = []
    for role in roles:
        badges = _get_role_badges(role.permissions)

        # Build detailed permissions badges with neutral styling
        detailed_perms = []
        for perm_name, perm_value in ALL_PERMISSIONS.items():
            if bool(role.permissions & perm_value) or bool(role.permissions & (1 << 3)):
                if perm_name in high_risk_perms:
                    badge_color = "bg-error/20 text-error border-error/30"
                elif perm_name in medium_risk_perms:
                    badge_color = "bg-warning/20 text-warning border-warning/30"
                else:
                    badge_color = "bg-info/20 text-info border-info/30"

                detailed_perms.append(
                    Span(
                        perm_name,
                        cls=f"inline-flex justify-center items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border {badge_color} w-full",
                    )
                )

        if detailed_perms:
            perms_ui = Div(*detailed_perms, cls="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2 mt-2")
        else:
            perms_ui = Div(Span("No explicit permissions", cls="opacity-50 text-xs italic"), cls="mt-2")

        # The row header (summary) mimics the table headers exactly
        role_summary_ui = Summary(
            Div(
                Div(
                    Span("▶", cls="text-[8px] opacity-40 mr-2 group-open:rotate-90 transition-transform inline-block"),
                    role.name,
                    cls="col-span-4 font-bold truncate flex items-center",
                    style=f"color: #{role.color:06x}" if role.color else "",
                ),
                Div(str(role.id), cls="col-span-3 opacity-70 font-mono text-xs truncate"),
                Div(str(role.position), cls="col-span-1 opacity-70"),
                Div(*badges, cls="col-span-2 flex flex-wrap items-center"),
                Div("✅" if role.is_hoisted else "", cls="col-span-1 text-center"),
                Div("✅" if role.is_managed else "", cls="col-span-1 text-center"),
                cls="grid grid-cols-12 w-full items-center gap-2",
            ),
            cls="px-4 py-3 hover:bg-base-200/50 transition-colors cursor-pointer list-none",
        )

        detail_panel = Div(perms_ui, cls="px-4 pb-4 pt-1 bg-base-300/20")

        role_rows.append(Details(role_summary_ui, detail_panel, cls="group border-b border-white/5"))

    guild_section = Div(
        # Header Row mimicking a table
        Div(
            Div("Name", cls="col-span-4 font-bold"),
            Div("ID", cls="col-span-3 font-bold"),
            Div("Pos", cls="col-span-1 font-bold"),
            Div("Key Perms", cls="col-span-2 font-bold"),
            Div("Sidebar", cls="col-span-1 font-bold text-center"),
            Div("Bot/Int", cls="col-span-1 font-bold text-center"),
            cls="grid grid-cols-12 gap-2 px-4 py-2 text-xs uppercase opacity-70 border-b border-white/10 bg-base-300/30",
        ),
        Div(*role_rows, cls="text-sm"),
        cls="w-full flex flex-col border border-white/10 rounded-lg overflow-hidden",
    )

    return Accordion(
        "Guild Roles",
        Div(_get_common_legend(for_roles=True), guild_section),
        open=False,
        id=f"guild-admin-audit-roles-{guild_id}",
    )


def guild_admin_audit_channels_widget(guild_id: int):
    """Displays Discord server channels for a specific guild.

    Groups channels by their parent category and visually indicates inherited
    versus explicit permission overwrites using FastHTML components.
    """
    with Session(engine) as session:
        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()

    if not channels:
        return Accordion(
            "Guild Channels",
            Div("No channels found for this server.", cls="opacity-70 text-sm mt-2"),
            open=False,
            id=f"guild-admin-audit-channels-{guild_id}",
        )

    channels = sorted(channels, key=lambda x: x.position)

    # Group by Category
    categories = {c.id: c for c in channels if c.type == "category"}
    uncategorized = []
    nested: dict[int, list[DiscordChannel]] = {}
    for c in channels:
        if c.type == "category":
            continue
        if c.parent_id:
            if c.parent_id not in nested:
                nested[c.parent_id] = []
            nested[c.parent_id].append(c)
        else:
            uncategorized.append(c)

    channel_rows = []

    def _build_overwrites_ui(overwrites_str, guild_id):
        is_private = False
        overwrites_ui = Span("-", cls="opacity-30 text-xs")
        detailed_perms_by_target = {}

        try:
            if overwrites_str:
                ov = json.loads(overwrites_str)
                if ov and len(ov) > 0:
                    ov_badges = []
                    # Check if @everyone is denied View Channel (1 << 10)
                    everyone_ov = ov.get(str(guild_id))
                    if everyone_ov and (everyone_ov.get("deny", 0) & (1 << 10)):
                        is_private = True

                    for target_id, access in ov.items():
                        name = access.get("name", target_id)
                        allow_val = access.get("allow", 0)
                        deny_val = access.get("deny", 0)

                        allow_count = allow_val.bit_count() if hasattr(int, "bit_count") else bin(allow_val).count("1")
                        deny_count = deny_val.bit_count() if hasattr(int, "bit_count") else bin(deny_val).count("1")

                        desc = []
                        if allow_count:
                            desc.append(f"{allow_count} Allowed")
                        if deny_count:
                            desc.append(f"{deny_count} Denied")
                        title_text = ", ".join(desc) if desc else "No Overrides"

                        color_cls = "badge-ghost"
                        if allow_count > 0 and deny_count == 0:
                            color_cls = "badge-success"
                        elif deny_count > 0 and allow_count == 0:
                            color_cls = "badge-error"
                        elif allow_count > 0 and deny_count > 0:
                            color_cls = "badge-warning"

                        # Build specific permissions UI for this target
                        target_detailed_perms = []
                        for perm_name, perm_value in ALL_PERMISSIONS.items():
                            if allow_val & perm_value:
                                target_detailed_perms.append(
                                    Span(
                                        perm_name,
                                        cls="inline-flex justify-center items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-success/20 text-success border border-success/30 w-full",
                                    )
                                )
                            elif deny_val & perm_value:
                                target_detailed_perms.append(
                                    Span(
                                        perm_name,
                                        cls="inline-flex justify-center items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-error/20 text-error border border-error/30 w-full",
                                    )
                                )

                        if target_detailed_perms:
                            detailed_perms_by_target[name] = Div(
                                *target_detailed_perms, cls="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2 mt-1"
                            )

                        ov_badges.append(
                            Span(
                                name,
                                cls=f"badge badge-sm px-2 rounded-md {color_cls} mr-1 mb-1 opacity-90",
                                title=title_text,
                            )
                        )
                    overwrites_ui = Div(*ov_badges, cls="flex flex-wrap")
        except Exception:
            logging.warning("Failed to parse channel overwrites", exc_info=True)
        return is_private, overwrites_ui, detailed_perms_by_target

    def channel_row(chan, indent=0, is_synced=False):
        icon = "📢"
        if "voice" in str(chan.type):
            icon = "🔊"
        elif "text" in str(chan.type):
            icon = "💬"
        elif "stage" in str(chan.type):
            icon = "🎭"
        elif "forum" in str(chan.type):
            icon = "🏛️"

        if is_synced:
            is_private, _, detailed_perms = _build_overwrites_ui(chan.overwrites, guild_id)
            overwrites_ui = Span(
                "Synced",
                cls="badge badge-sm badge-ghost opacity-50 rounded-md",
                title="Has identical explicit overwrites to its parent category.",
            )
        else:
            is_private, overwrites_ui, detailed_perms = _build_overwrites_ui(chan.overwrites, guild_id)

        if is_private:
            icon = f"🔒 {icon}"
            name_cls = "font-bold text-error"
        else:
            name_cls = "opacity-70"

        # Expandable Detail Content
        if not is_synced and detailed_perms:
            perms_sections = []
            for target_name, perms_div in detailed_perms.items():
                perms_sections.append(
                    Div(H5(target_name, cls="text-xs font-bold opacity-80 mb-1"), perms_div, cls="mb-3 last:mb-0")
                )
            detail_panel = Div(*perms_sections, cls="px-4 pb-4 pt-1 bg-base-300/20")

            summary_ui = Summary(
                Div(
                    Div(
                        Span(
                            "▶", cls="text-[8px] opacity-40 mr-2 group-open:rotate-90 transition-transform inline-block"
                        ),
                        icon,
                        Span(chan.name, cls=f"ml-2 {name_cls}"),
                        cls="col-span-5 flex items-center",
                        style=f"padding-left: {indent}em",
                    ),
                    Div(overwrites_ui, cls="col-span-7"),
                    cls="grid grid-cols-12 w-full items-center gap-2",
                ),
                cls="px-4 py-2 hover:bg-base-200/50 transition-colors cursor-pointer list-none",
            )

            return Details(summary_ui, detail_panel, cls="group border-b border-white/5")
        else:
            # Not expandable if synced or no detailed perms
            return Div(
                Div(
                    Span(" ", cls="mr-4 inline-block"),
                    icon,
                    Span(chan.name, cls=f"ml-2 {name_cls}"),
                    cls="col-span-5 flex items-center",
                    style=f"padding-left: {indent}em",
                ),
                Div(overwrites_ui, cls="col-span-7"),
                cls="grid grid-cols-12 gap-2 px-4 py-2 border-b border-white/5 hover:bg-base-200/50 transition-colors items-center",
            )

    for c in uncategorized:
        channel_rows.append(channel_row(c))
    for cat_id, category in categories.items():
        _, cat_overwrites_ui, cat_detailed_perms = _build_overwrites_ui(category.overwrites, guild_id)

        # Expandable Detail Content for Category
        if cat_detailed_perms:
            perms_sections = []
            for target_name, perms_div in cat_detailed_perms.items():
                perms_sections.append(
                    Div(H5(target_name, cls="text-xs font-bold opacity-80 mb-1"), perms_div, cls="mb-3 last:mb-0")
                )
            detail_panel = Div(*perms_sections, cls="px-4 pb-4 pt-1 bg-base-300/20")

            summary_ui = Summary(
                Div(
                    Div(
                        Span(
                            "▶", cls="text-[8px] opacity-40 mr-2 group-open:rotate-90 transition-transform inline-block"
                        ),
                        Span("📁", cls="mr-2 opacity-50"),
                        B(category.name.upper()),
                        cls="col-span-5 flex items-center text-xs font-bold opacity-60 ml-[-0.5em]",
                    ),
                    Div(cat_overwrites_ui, cls="col-span-7"),
                    cls="grid grid-cols-12 w-full items-center gap-2",
                ),
                cls="px-4 py-2 hover:bg-base-200/50 transition-colors cursor-pointer list-none bg-base-content/5",
            )

            channel_rows.append(Details(summary_ui, detail_panel, cls="group border-b border-white/5"))
        else:
            channel_rows.append(
                Div(
                    Div(
                        Span(" ", cls="mr-4 inline-block"),
                        Span("📁", cls="mr-2 opacity-50"),
                        B(category.name.upper()),
                        cls="col-span-5 flex items-center text-xs font-bold opacity-60 ml-[-0.5em]",
                    ),
                    Div(cat_overwrites_ui, cls="col-span-7"),
                    cls="grid grid-cols-12 gap-2 px-4 py-2 bg-base-content/5 border-b border-white/5 items-center",
                )
            )

        try:
            cat_ov_dict = json.loads(category.overwrites) if category.overwrites else {}
        except Exception:
            cat_ov_dict = {}

        for child in nested.get(cat_id, []):
            try:
                child_ov_dict = json.loads(child.overwrites) if child.overwrites else {}
            except Exception:
                child_ov_dict = {}

            # Identical explicit overwrites
            is_synced = cat_ov_dict == child_ov_dict
            channel_rows.append(channel_row(child, indent=1.5, is_synced=is_synced))

    guild_section = Div(
        # Header Row mimicking a table
        Div(
            Div("Channel", cls="col-span-5 font-bold"),
            Div("Overwrites", cls="col-span-7 font-bold"),
            cls="grid grid-cols-12 gap-2 px-4 py-2 text-xs uppercase opacity-70 border-b border-white/10 bg-base-300/30",
        ),
        Div(*channel_rows, cls="text-sm"),
        cls="w-full flex flex-col border border-white/10 rounded-lg overflow-hidden",
    )

    return Accordion(
        "Guild Channels",
        Div(_get_common_legend(for_roles=False), guild_section),
        open=False,
        id=f"guild-admin-audit-channels-{guild_id}",
    )


def guild_admin_security_overview_widget(guild_id: int):
    """Provides a high-level summary of the server's security posture."""
    with Session(engine) as session:
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()

        if not roles and not channels:
            return Card(
                "Start Audit to view Security Overview",
                Div("No data found for this server.", cls="opacity-70 text-sm mt-2"),
            )

        evaluation = SecurityRuleEngine.evaluate(guild_id, session)
        score = evaluation["score"]
        alerts = evaluation["alerts"]

    # Calculate stats
    admin_roles_count = sum(1 for r in roles if (r.permissions & (1 << 3)) and not r.is_managed)
    private_channels_count = 0
    for c in channels:
        if c.overwrites:
            try:
                ov = json.loads(c.overwrites)
                everyone_ov = ov.get(str(guild_id))
                if everyone_ov and (everyone_ov.get("deny", 0) & (1 << 10)):
                    private_channels_count += 1
            except Exception:
                logging.warning("Failed to parse overwrites for channel %s", c.id, exc_info=True)

    DISCORD_MAX_ROLES = 250
    DISCORD_MAX_CHANNELS = 500

    gauges_row = Div(
        HealthScoreArc(score, len(alerts)),
        cls="flex justify-center items-center w-full mb-1",
    )

    stats_grid = Div(
        ProgressBarStat("Total Roles", len(roles), DISCORD_MAX_ROLES),
        ProgressBarStat("Total Channels", len(channels), DISCORD_MAX_CHANNELS),
        Div(
            SegmentedDigit(admin_roles_count, "Admin Roles", "text-error"),
            SegmentedDigit(private_channels_count, "Private Channels", "text-info"),
            cls="grid grid-cols-2 gap-3 w-full",
        ),
        cls="flex flex-col gap-3 w-full flex-1",
    )

    categories_list = ["Exposure", "Pings", "Roles", "Integrations"]
    severities_list = ["High", "Medium", "Low"]
    matrix = {cat.lower(): {sev.lower(): 0 for sev in severities_list} for cat in categories_list}
    for a in alerts:
        a_cat = a.get("category", "").lower()
        a_sev = a.get("severity", "").lower()
        if a_cat in matrix and a_sev in matrix[a_cat]:
            matrix[a_cat][a_sev] += 1

    def format_count(count):
        if count == 0:
            return Span("0", cls="opacity-30 text-base-content/40 font-normal")
        return Span(str(count), cls="font-semibold")

    table_rows = []
    for cat in categories_list:
        cat_lower = cat.lower()
        table_rows.append(
            Tr(
                Td(cat, cls="text-left font-medium opacity-80"),
                Td(format_count(matrix[cat_lower]["high"])),
                Td(format_count(matrix[cat_lower]["medium"])),
                Td(format_count(matrix[cat_lower]["low"])),
            )
        )

    breakdown_table = Table(
        Thead(
            Tr(
                Th("Category", cls="text-left"),
                Th("High", cls="text-error font-bold"),
                Th("Medium", cls="text-warning font-semibold"),
                Th("Low", cls="text-info font-medium"),
            )
        ),
        Tbody(*table_rows),
        cls="table table-xs w-full border border-base-300 bg-base-200/30 rounded-md",
    )

    breakdown_section = Div(
        Div(
            "Alerts Breakdown",
            cls="text-[10px] font-bold uppercase tracking-wider opacity-60 mb-2 border-t border-white/10 pt-2 w-full text-center",
        ),
        breakdown_table,
        cls="w-full flex flex-col items-center",
    )

    return Card(
        "Security Overview",
        Div(
            gauges_row,
            breakdown_section,
            stats_grid,
            cls="flex flex-col gap-4 items-center w-full h-full min-h-0",
        ),
        id=f"guild-admin-security-overview-{guild_id}",
        cls="min-h-[480px] max-h-[640px] h-full",
    )


def guild_admin_audit_permissions_widget(guild_id: int):
    """Displays a matrix correlating permissions to roles."""
    with Session(engine) as session:
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()

    if not roles:
        return Accordion(
            "Permissions Matrix",
            Div("No roles found for this server.", cls="opacity-70 text-sm mt-2"),
            open=False,
            id=f"guild-admin-audit-permissions-{guild_id}",
        )

    # Standardize sort: highly privileged / high position roles first
    roles = sorted(roles, key=lambda x: x.position, reverse=True)

    def generate_matrix_rows(permissions_dict):
        matrix_rows = []
        for perm_name, perm_value in permissions_dict.items():
            roles_with_perm = []
            for role in roles:
                has_perm = bool(role.permissions & perm_value) or bool(role.permissions & (1 << 3))

                if has_perm:
                    if role.permissions & (1 << 3):
                        badge_cls = "badge-error text-error-content"
                    elif role.is_managed:
                        badge_cls = "badge-warning text-warning-content"
                    else:
                        badge_cls = "badge-neutral text-neutral-content"
                    badge = Span(
                        role.name,
                        cls=f"badge {badge_cls} inline-flex items-center px-2 py-0.5 rounded-md mr-1 mb-1 text-xs font-semibold",
                    )
                    roles_with_perm.append(badge)

            if not roles_with_perm:
                roles_ui = Span("None", cls="opacity-50 text-xs italic")
            else:
                roles_ui = Div(*roles_with_perm, cls="flex flex-wrap")

            highlight_class = (
                "font-semibold text-base-content" if perm_name == "Administrator" else "opacity-80 font-medium"
            )

            matrix_rows.append(
                Tr(
                    Td(Span(perm_name, cls=highlight_class)),
                    Td(roles_ui),
                    cls="border-b border-white/5 hover:bg-base-200/50 transition-colors",
                )
            )
        return matrix_rows

    primary_table = Div(
        Table(
            Thead(Tr(Th("Permission"), Th("Roles Granted"))),
            Tbody(*generate_matrix_rows(SENSITIVE_PERMISSIONS)),
            cls="table table-sm w-full mt-2",
        )
    )

    secondary_table = Details(
        Summary(
            "View All Permissions",
            cls="cursor-pointer font-bold opacity-80 mt-4 mb-2 hover:opacity-100 transition-opacity",
        ),
        Div(
            Table(
                Thead(Tr(Th("Permission"), Th("Roles Granted"))),
                Tbody(*generate_matrix_rows(OTHER_PERMISSIONS)),
                cls="table table-sm w-full",
            ),
            cls="mt-2 border border-white/10 rounded-lg p-2 bg-base-300/30",
        ),
    )

    legend_block = Div(
        Span("Badge Colors: ", cls="text-xs font-bold opacity-70 mr-1"),
        Span(
            "Red (Administrator)",
            cls="badge badge-error text-error-content badge-xs mr-2 font-semibold px-2 py-0.5 rounded-md",
        ),
        Span(
            "Yellow (Bot-owned)",
            cls="badge badge-warning text-warning-content badge-xs mr-2 font-semibold px-2 py-0.5 rounded-md",
        ),
        Span(
            "Gray (Standard)",
            cls="badge badge-neutral text-neutral-content badge-xs font-semibold px-2 py-0.5 rounded-md",
        ),
        cls="flex items-center flex-wrap mb-4 bg-base-200/50 p-2.5 rounded-md border border-base-300",
    )

    return Accordion(
        "Permissions Matrix",
        Div(
            P(
                "Overview indicating which roles currently possess sensitive administrative or moderation permissions.",
                cls="text-xs opacity-70 mb-2",
            ),
            legend_block,
            primary_table,
            secondary_table,
        ),
        open=False,
        id=f"guild-admin-audit-permissions-{guild_id}",
    )


class SecurityRule:
    name: str = ""
    category: str = ""
    severity: str = ""

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        raise NotImplementedError


class CategoryPermissionBaseline(SecurityRule):
    name = "Category Permission Baseline"
    category = "exposure"
    severity = "medium"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
        categories = {c.id: c for c in channels if c.type == "category"}
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        role_map = {str(r.id): r.name for r in roles}
        alerts = []

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

                    if target_id in role_map:
                        display_name = f"Role '{role_map[target_id]}'"
                    elif t_name:
                        if t_type == "role":
                            display_name = f"Role '{t_name}'"
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
                        }
                    )
        return alerts


def get_effective_channel_permissions(
    role: DiscordRole,
    channel: DiscordChannel,
    everyone_role: Optional[DiscordRole],
    overwrites: dict,
    parent_overwrites: Optional[dict] = None,
) -> int:
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
        return p

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
    return p


class PublicAnnouncementProtection(SecurityRule):
    name = "Public Announcement Protection"
    category = "pings"
    severity = "high"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        ann_channel_ids = []
        sep_role_id = None
        if config:
            try:
                ann_channel_ids = json.loads(config.announcement_channel_ids or "[]")
            except Exception:  # noqa: S110
                pass
            sep_role_id = config.staff_separator_role_id

        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        everyone_role = next((r for r in roles if r.position == 0 or r.id == guild_id), None)

        sep_pos = None
        if sep_role_id:
            sep_role = next((r for r in roles if r.id == sep_role_id), None)
            if sep_role:
                sep_pos = sep_role.position

        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
        categories = {c.id: c for c in channels if c.type == "category"}
        alerts = []

        for c in channels:
            if c.type == "category":
                continue
            is_ann = (c.id in ann_channel_ids) or c.type == "news"
            if not is_ann:
                continue

            try:
                overwrites = json.loads(c.overwrites or "{}")
            except Exception:  # noqa: S112
                continue

            # Resolve parent category overwrites for inheritance
            parent_overwrites = None
            parent = categories.get(c.parent_id) if c.parent_id else None
            if parent:
                try:
                    parent_overwrites = json.loads(parent.overwrites or "{}")
                except Exception:  # noqa: S110
                    pass

            for r in roles:
                is_everyone = r.position == 0 or r.id == guild_id
                is_below_sep = sep_pos is not None and r.position < sep_pos
                if is_everyone or is_below_sep:
                    p = get_effective_channel_permissions(r, c, everyone_role, overwrites, parent_overwrites)
                    # Skip alert if the role can't even see the channel
                    if not (p & (1 << 10)):
                        continue
                    # Check for send messages (1<<11), mention everyone (1<<17), or global Administrator (1<<3)
                    if (p & (1 << 11)) or (p & (1 << 17)) or (r.permissions & (1 << 3)):
                        alerts.append(
                            {
                                "rule": self.name,
                                "category": self.category,
                                "severity": self.severity,
                                "message": f"Announcement channel #{c.name} allows role '{r.name}' to send messages or mention everyone.",
                                "details": f"Role '{r.name}' (position {r.position}) has effective permissions {decode_permissions(p)} in announcement channel.",
                                "action_buttons": [],
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
                p = get_effective_channel_permissions(r, c, everyone_role, overwrites, parent_overwrites)
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
                        }
                    )
        return alerts


class UnauthorizedChatPings(SecurityRule):
    name = "Unauthorized Chat Pings in Non-Text Locations"
    category = "pings"
    severity = "medium"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        sep_role_id = config.staff_separator_role_id if config else None

        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        everyone_role = next((r for r in roles if r.position == 0 or r.id == guild_id), None)

        sep_pos = None
        if sep_role_id:
            sep_role = next((r for r in roles if r.id == sep_role_id), None)
            if sep_role:
                sep_pos = sep_role.position

        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
        categories = {c.id: c for c in channels if c.type == "category"}
        alerts = []

        for c in channels:
            if not any(k in c.type.lower() for k in ["voice", "thread", "forum"]):
                continue

            try:
                overwrites = json.loads(c.overwrites or "{}")
            except Exception:  # noqa: S112
                continue

            # Resolve parent category overwrites for inheritance
            parent_overwrites = None
            parent = categories.get(c.parent_id) if c.parent_id else None
            if parent:
                try:
                    parent_overwrites = json.loads(parent.overwrites or "{}")
                except Exception:  # noqa: S110
                    pass

            for r in roles:
                is_everyone = r.position == 0 or r.id == guild_id
                is_below_sep = sep_pos is not None and r.position < sep_pos
                if is_everyone or is_below_sep:
                    p = get_effective_channel_permissions(r, c, everyone_role, overwrites, parent_overwrites)
                    # Skip alert if the role can't even see the channel
                    if not (p & (1 << 10)):
                        continue
                    if (p & (1 << 11)) or (p & (1 << 17)) or (r.permissions & (1 << 3)):
                        alerts.append(
                            {
                                "rule": self.name,
                                "category": self.category,
                                "severity": self.severity,
                                "message": f"Non-text location #{c.name} allows role '{r.name}' to send messages or mention everyone.",
                                "details": f"Channel of type '{c.type}' allows non-admin role '{r.name}' to Send Messages or Mention Everyone. Allowed permissions: {decode_permissions(p)}.",
                                "action_buttons": [],
                            }
                        )
        return alerts


class LowTierRolePrivileges(SecurityRule):
    name = "Low-Tier Role Privileges"
    category = "roles"
    severity = "high"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        sep_role_id = config.staff_separator_role_id if config else None
        if not sep_role_id:
            return []

        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        sep_role = next((r for r in roles if r.id == sep_role_id), None)
        if not sep_role:
            return []

        sep_pos = sep_role.position
        alerts = []
        mask = (1 << 3) | (1 << 5) | (1 << 28) | (1 << 4) | (1 << 1) | (1 << 2) | (1 << 17)

        for r in roles:
            if r.position < sep_pos and (r.permissions & mask) != 0:
                alerts.append(
                    {
                        "rule": self.name,
                        "category": self.category,
                        "severity": self.severity,
                        "message": f"Low-tier role '{r.name}' has sensitive permissions.",
                        "details": f"Role '{r.name}' (position {r.position}) has sensitive permissions: {decode_permissions(r.permissions & mask)}.",
                        "action_buttons": [],
                    }
                )
        return alerts


class GeneralRoleMentionability(SecurityRule):
    name = "General Role Mentionability"
    category = "pings"
    severity = "low"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        sep_role_id = config.staff_separator_role_id if config else None
        if not sep_role_id:
            return []

        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        sep_role = next((r for r in roles if r.id == sep_role_id), None)
        if not sep_role:
            return []

        sep_pos = sep_role.position
        alerts = []

        for r in roles:
            if r.position < sep_pos and not r.is_managed and r.is_mentionable:
                alerts.append(
                    {
                        "rule": self.name,
                        "category": self.category,
                        "severity": self.severity,
                        "message": f"Low-tier role '{r.name}' is mentionable.",
                        "details": f"Role '{r.name}' is a non-admin role set to mentionable, posing a mass ping raid vulnerability.",
                        "action_buttons": [],
                    }
                )
        return alerts


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
            HoneypotChannel = None

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


class OverPrivilegedBotIntegrations(SecurityRule):
    name = "Over-privileged Bot Integrations"
    category = "integrations"
    severity = "medium"

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        alerts = []
        mask = (1 << 3) | (1 << 5) | (1 << 28) | (1 << 4)

        for r in roles:
            if r.is_managed and (r.permissions & mask) != 0:
                alerts.append(
                    {
                        "rule": self.name,
                        "category": self.category,
                        "severity": self.severity,
                        "message": f"Bot role '{r.name}' has excessive privileges.",
                        "details": f"Managed integration role '{r.name}' has sensitive permissions: {decode_permissions(r.permissions & mask)}.",
                        "action_buttons": [],
                    }
                )
        return alerts


SECURITY_RULES = [
    CategoryPermissionBaseline,
    PublicAnnouncementProtection,
    ExposedStaffChannels,
    UnauthorizedChatPings,
    LowTierRolePrivileges,
    GeneralRoleMentionability,
    SuggestiveHoneypotIntegration,
    OverPrivilegedBotIntegrations,
]


class EvaluationCache(TTLCache):
    def pop(self, key, default=None):
        try:
            g_id = int(key)
            prefix = f"{g_id}:"
        except (ValueError, TypeError):
            prefix = None

        to_remove = []
        for k in list(self.keys()):
            if k == key:
                to_remove.append(k)
            elif prefix and isinstance(k, str) and k.startswith(prefix):
                to_remove.append(k)

        val = default
        for k in to_remove:
            val = super().pop(k, default)
        return val

    def __contains__(self, key):
        try:
            g_id = int(key)
            prefix = f"{g_id}:"
        except (ValueError, TypeError):
            prefix = None

        for k in list(self.keys()):
            if k == key:
                return True
            if prefix and isinstance(k, str) and k.startswith(prefix):
                return True
        return False

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            try:
                g_id = int(key)
                prefix = f"{g_id}:"
            except (ValueError, TypeError):
                prefix = None

            if prefix:
                for k in list(self.keys()):
                    if isinstance(k, str) and k.startswith(prefix):
                        return super().__getitem__(k)
            raise

    def __delitem__(self, key):
        try:
            super().__delitem__(key)
        except KeyError:
            try:
                g_id = int(key)
                prefix = f"{g_id}:"
            except (ValueError, TypeError):
                prefix = None

            if prefix:
                to_remove = [k for k in list(self.keys()) if isinstance(k, str) and k.startswith(prefix)]
                if to_remove:
                    for k in to_remove:
                        super().__delitem__(k)
                    return
            raise


class SecurityRuleEngine:
    _evaluation_cache: EvaluationCache = EvaluationCache(maxsize=256, ttl=120)

    def __init__(self):
        self.rules = [rule_cls() for rule_cls in SECURITY_RULES]

    @classmethod
    def invalidate(cls, guild_id: int) -> None:
        """Remove cached evaluation for a guild, if present."""
        try:
            guild_id = int(guild_id)
        except (ValueError, TypeError):
            return
        cls._evaluation_cache.pop(guild_id, None)

    @staticmethod
    def evaluate(guild_id: int, session: Session, include_overridden: bool = False) -> dict:
        guild_id = int(guild_id)

        # Calculate checksum based on DB records
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
        configs = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).all()
        overrides = session.exec(select(SecurityAlertOverride).where(SecurityAlertOverride.guild_id == guild_id)).all()

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
        checksum = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

        cache_key = f"{guild_id}:{checksum}:{include_overridden}"
        if cache_key in SecurityRuleEngine._evaluation_cache:
            return SecurityRuleEngine._evaluation_cache[cache_key]

        res = SecurityRuleEngine().run_all(guild_id, session, include_overridden=include_overridden)
        SecurityRuleEngine._evaluation_cache[cache_key] = res
        return res

    def run_all(self, guild_id: int, session: Session, include_overridden: bool = False) -> dict:
        alerts = []
        for rule in self.rules:
            try:
                rule_alerts = rule.evaluate(guild_id, session)
                alerts.extend(rule_alerts)
            except Exception as e:
                logging.exception(f"Error evaluating rule {rule.name}: {e}")

        # Compute hash for every alert and filter if not include_overridden
        overrides = session.exec(select(SecurityAlertOverride).where(SecurityAlertOverride.guild_id == guild_id)).all()
        override_hashes = {o.alert_hash for o in overrides}

        filtered_alerts = []
        for alert in alerts:
            ahash = hashlib.sha256(
                f"{alert.get('rule')}:{alert.get('category')}:{alert.get('message')}".encode("utf-8")
            ).hexdigest()
            alert["alert_hash"] = ahash
            if include_overridden or ahash not in override_hashes:
                filtered_alerts.append(alert)

        # Now compute score only on non-overridden alerts!
        num_high = 0
        num_medium = 0
        num_low = 0
        for alert in filtered_alerts:
            if alert["alert_hash"] not in override_hashes:
                details = str(alert.get("details", ""))
                if "[INERT" in details:
                    continue
                sev = alert.get("severity", "").lower()
                if sev == "high":
                    num_high += 1
                elif sev == "medium":
                    num_medium += 1
                elif sev == "low":
                    num_low += 1

        score = 100 - (15 * num_high + 10 * num_medium + 5 * num_low)
        score = max(0, min(100, score))
        severity_order = {"high": 0, "medium": 1, "low": 2}
        filtered_alerts.sort(key=lambda a: severity_order.get(a.get("severity", "").lower(), 3))
        return {"score": score, "alerts": filtered_alerts}


def format_details(details: str) -> FT:
    if not details:
        return ""

    def make_perm_badge(p_name: str) -> FT:
        p_clean = p_name.strip("' ")
        if p_clean.lower() == "none":
            return Span("None", cls="text-xs opacity-50 font-mono")
        if p_clean in high_risk_perms:
            return Span(
                p_clean,
                cls="badge badge-error badge-outline badge-sm h-auto py-1 px-2.5 mr-1 mb-1 font-semibold shadow-sm",
            )
        elif p_clean in medium_risk_perms:
            return Span(
                p_clean, cls="badge badge-warning badge-outline badge-sm h-auto py-1 px-2.5 mr-1 mb-1 font-semibold"
            )
        else:
            return Span(
                p_clean, cls="badge badge-info badge-outline badge-sm h-auto py-1 px-2.5 mr-1 mb-1 font-semibold"
            )

    def group_permissions(perms_list: list[str]) -> list[str]:
        high = []
        medium = []
        low = []
        has_none = False
        for p in perms_list:
            p_clean = p.strip("' ")
            if p_clean.lower() == "none":
                has_none = True
            elif p_clean in high_risk_perms:
                high.append(p)
            elif p_clean in medium_risk_perms:
                medium.append(p)
            else:
                low.append(p)
        result = high + medium + low
        if not result and has_none:
            result = ["none"]
        return result

    # 1. Check if CategoryPermissionBaseline
    if "Leaked allows:" in details:
        parts = details.split("Leaked allows:")
        prefix = parts[0].strip()
        rest = parts[1].split("leaked denies:")
        allows_str = rest[0].strip()
        denies_str = rest[1].strip() if len(rest) > 1 else ""

        if allows_str.endswith(","):
            allows_str = allows_str[:-1]
        if denies_str.endswith("."):
            denies_str = denies_str[:-1]

        allows = group_permissions([p.strip("' ") for p in allows_str.split(",") if p.strip()])
        denies = group_permissions([p.strip("' ") for p in denies_str.split(",") if p.strip()])

        allows_badges = [make_perm_badge(p) for p in allows]
        denies_badges = [make_perm_badge(p) for p in denies]

        return Div(
            P(prefix, cls="text-sm font-semibold text-secondary/90 mb-2"),
            Div(
                Span("Leaked Allows: ", cls="text-xs font-bold text-secondary mr-2"),
                Div(*allows_badges, cls="inline-flex flex-wrap items-center"),
                cls="mb-1.5 flex flex-wrap items-center",
            ),
            Div(
                Span("Leaked Denies: ", cls="text-xs font-bold text-secondary mr-2"),
                Div(*denies_badges, cls="inline-flex flex-wrap items-center"),
                cls="flex flex-wrap items-center",
            ),
            cls="p-3 bg-black/40 rounded-md border border-neutral-700/50 mt-2",
        )

    # 2. Check other rules that contain explicit list markers
    perms_marker = None
    if "Allowed permissions:" in details:
        perms_marker = "Allowed permissions:"
    elif "sensitive permissions:" in details:
        perms_marker = "sensitive permissions:"
    elif "effective permissions" in details:
        perms_marker = "effective permissions"

    if perms_marker:
        parts = details.split(perms_marker)
        prefix = parts[0].strip()
        perms_str = parts[1].strip()
        if perms_str.endswith("."):
            perms_str = perms_str[:-1]
        if perms_str.startswith(":"):
            perms_str = perms_str[1:].strip()

        perms = group_permissions([p.strip("' ") for p in perms_str.split(",") if p.strip()])
        perms_badges = [make_perm_badge(p) for p in perms]

        return Div(
            P(prefix, cls="text-sm font-semibold text-secondary/90 mb-2"),
            Div(
                Span("Permissions: ", cls="text-xs font-bold text-secondary mr-2"),
                Div(*perms_badges, cls="inline-flex flex-wrap items-center"),
                cls="flex flex-wrap items-center",
            ),
            cls="p-3 bg-black/40 rounded-md border border-neutral-700/50 mt-2",
        )

    # 3. Highlight single-quoted terms (e.g. role names, channel names) in default text
    pattern = r"'([^']+)'"
    matches = re.findall(pattern, details)
    if matches:
        formatted_parts = []
        last_idx = 0
        for match in re.finditer(pattern, details):
            # Text before the match
            if match.start() > last_idx:
                formatted_parts.append(Span(details[last_idx : match.start()], cls="text-xs opacity-80"))
            # The matched text styled
            formatted_parts.append(
                Span(
                    match.group(1),
                    cls="text-xs text-accent font-bold bg-accent/10 px-1.5 py-0.5 rounded border border-accent/20 mx-0.5",
                )
            )
            last_idx = match.end()
        if last_idx < len(details):
            formatted_parts.append(Span(details[last_idx:], cls="text-xs opacity-80"))
        return Div(*formatted_parts, cls="p-3 bg-black/40 rounded-md border border-neutral-700/50 mt-2 leading-relaxed")

    # 4. Fallback style
    return Div(
        Span(details, cls="text-xs opacity-80"), cls="p-3 bg-black/40 rounded-md border border-neutral-700/50 mt-2"
    )


def format_message(text: str) -> FT:
    if not text:
        return ""

    highlights = []

    # 1. Channel names starting with #
    for m in re.finditer(r"#([a-zA-Z0-9_-]+)", text):
        highlights.append((m.start(), m.end(), m.group(0), "channel"))

    # 2. Quoted names like 'Role'
    for m in re.finditer(r"'([^']+)'", text):
        highlights.append((m.start(), m.end(), m.group(1), "quote"))

    # 3. Role name after "is visible to "
    for m in re.finditer(r"is visible to ([^.]+)", text):
        highlights.append((m.start(1), m.end(1), m.group(1), "role"))

    # 4. Category name after "compared to parent category "
    for m in re.finditer(r"compared to parent category ([^.]+)", text):
        highlights.append((m.start(1), m.end(1), m.group(1), "category"))

    # Sort highlights by starting index
    highlights = sorted(highlights, key=lambda x: x[0])

    # Resolve overlaps (keep the first one)
    non_overlapping = []
    last_end = 0
    for start, end, val, kind in highlights:
        if start >= last_end:
            non_overlapping.append((start, end, val, kind))
            last_end = end

    # Rebuild the FT components
    formatted_parts = []
    last_idx = 0
    for start, end, val, kind in non_overlapping:
        if start > last_idx:
            formatted_parts.append(Span(text[last_idx:start]))

        formatted_parts.append(
            Span(val, cls="font-bold text-accent")
        )
        last_idx = end

    if last_idx < len(text):
        formatted_parts.append(Span(text[last_idx:]))

    return Span(*formatted_parts)


def _render_alerts_list(alerts: list[dict], guild_id: int) -> FT:
    if not alerts:
        return Div("No security alerts found.", cls="text-sm opacity-70 p-4 text-center")

    alert_elements = []
    for alert in alerts:
        sev = alert.get("severity", "").lower()
        if sev == "high":
            badge_cls = "badge-error"
            border_cls = "border-error/30 bg-error/10 text-error-content"
        elif sev == "medium":
            badge_cls = "badge-warning"
            border_cls = "border-warning/30 bg-warning/10 text-warning-content"
        else:
            badge_cls = "badge-info"
            border_cls = "border-info/30 bg-info/10 text-info-content"

        # Action buttons
        buttons = []
        for btn in alert.get("action_buttons", []):
            buttons.append(Button(btn["text"], hx_post=btn["hx_post"], cls="btn btn-xs btn-outline btn-primary mr-2"))

        # Add Override button
        alert_hash = alert.get("alert_hash")
        if not alert_hash:
            alert_hash = hashlib.sha256(
                f"{alert.get('rule')}:{alert.get('category')}:{alert.get('message')}".encode("utf-8")
            ).hexdigest()
        buttons.append(
            Button(
                "Override",
                hx_get=f"/dashboard/{guild_id}/alerts/override-confirm?alert_hash={alert_hash}",
                hx_target="#modal-container",
                hx_swap="innerHTML",
                cls="btn btn-xs btn-outline btn-warning ml-auto",
            )
        )

        alert_elements.append(
            Div(
                Div(
                    Span(
                        alert.get("rule", "Security Alert"),
                        cls=f"badge {badge_cls} badge-sm px-2.5 py-1 mr-2 font-bold",
                    ),
                    Span(alert.get("category", "").upper(), cls="text-[10px] uppercase font-bold text-secondary tracking-wider"),
                    cls="flex items-center mb-1",
                ),
                P(format_message(alert.get("message", "")), cls="text-sm font-medium mb-1"),
                Details(
                    Summary(
                        Div(
                            Span("Details", cls="text-xs font-bold text-secondary uppercase tracking-wider"),
                            I(
                                cls="fa-solid fa-chevron-down text-[10px] text-secondary transition-transform group-open:rotate-180"
                            ),
                            cls="flex items-center gap-1.5 cursor-pointer hover:text-primary transition-all",
                        ),
                        cls="list-none outline-none select-none group",
                    ),
                    format_details(alert.get("details", "")),
                    cls="mb-2 group",
                )
                if alert.get("details")
                else "",
                Div(*buttons, cls="flex w-full items-center") if buttons else "",
                cls=f"p-3 rounded-md border-l-4 border {border_cls} mb-3 last:mb-0",
            )
        )
    return Div(*alert_elements)


def get_security_rules_modal(guild_id: int) -> FT:
    """Generates a modal detailing the security rules evaluated by the auditor."""
    rules_details = [
        {
            "name": "1. Category Permission Baseline",
            "category": "Exposure",
            "severity": "Medium",
            "desc": "Checks if a channel category grants permissions to non-staff roles beyond the server default.",
            "remediation": "Remove unnecessary category-level overwrites; prefer per-channel grants.",
        },
        {
            "name": "2. Public Announcement Protection",
            "category": "Pings",
            "severity": "High",
            "desc": "Verifies that non-staff roles cannot Send Messages, Mention Everyone, or @everyone in announcement channels.",
            "remediation": "Deny Send Messages and Mention Everyone for all non-staff roles in announcement channels.",
        },
        {
            "name": "3. Exposed Staff Channels",
            "category": "Exposure",
            "severity": "High",
            "desc": "Checks if a non-staff role has View Channel allowed in a channel listed in the staff channels configuration.",
            "remediation": "Explicitly deny View Channel for every non-staff role on staff channels.",
        },
        {
            "name": "4. Unauthorized Chat Pings in Non-Text Locations",
            "category": "Pings",
            "severity": "Medium",
            "desc": "Ensures non-staff roles cannot Send Messages in voice, stage, thread, or forum channels.",
            "remediation": "Deny Send Messages for non-staff roles on non-text channel types.",
        },
        {
            "name": "5. Low-Tier Role Privileges",
            "category": "Roles",
            "severity": "High",
            "desc": "Checks if a non-admin role has dangerous permissions like Administrator, Manage Server, Manage Roles, Manage Channels, Kick Members, Ban Members, or Mention Everyone.",
            "remediation": "Remove dangerous permissions from non-admin roles or promote the role above the lowest admin role.",
        },
        {
            "name": "6. General Role Mentionability",
            "category": "Pings",
            "severity": "Low",
            "desc": "Ensures non-admin, unmanaged roles do not have mentionable set to true.",
            "remediation": "Disable mentionability or restrict via channel overwrites.",
        },
        {
            "name": "7. Suggestive Honeypot Integration",
            "category": "Integrations",
            "severity": "Medium",
            "desc": "Flags if public discovery channels exist but the Honeypot extension is not enabled.",
            "remediation": "Enable the Honeypot extension or remove public discovery channels.",
        },
        {
            "name": "8. Over-privileged Bot Integrations",
            "category": "Integrations",
            "severity": "Medium",
            "desc": "Checks if a managed bot role has Administrator, Manage Server, Manage Roles, or Manage Channels permissions.",
            "remediation": "Reduce bot role permissions to the minimum required scope.",
        },
    ]

    modal_id = f"modal-security-rules-info-{guild_id}"
    close_button = Form(
        Button(I(cls="fa-solid fa-xmark"), cls="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"),
        method="dialog",
    )

    rule_elements = []
    for r in rules_details:
        sev = r["severity"].lower()
        if sev == "high":
            sev_cls = "badge-error"
        elif sev == "medium":
            sev_cls = "badge-warning"
        else:
            sev_cls = "badge-info"

        cat = r["category"].lower()
        if cat == "exposure":
            cat_cls = "badge-accent"
        elif cat == "pings":
            cat_cls = "badge-secondary"
        elif cat == "roles":
            cat_cls = "badge-primary"
        else:
            cat_cls = "badge-neutral"

        rule_elements.append(
            Div(
                H4(r["name"], cls="text-md font-bold text-base-content mb-1.5"),
                Div(
                    Span(r["severity"], cls=f"badge {sev_cls} badge-md px-4 py-2 font-bold shadow-sm h-auto text-xs"),
                    Span(
                        r["category"],
                        cls=f"badge {cat_cls} badge-outline badge-md px-4 py-2 font-semibold shadow-sm h-auto text-xs",
                    ),
                    cls="flex items-center gap-2 mb-3",
                ),
                P(r["desc"], cls="text-xs text-base-content/85 mb-3 leading-relaxed"),
                Div(
                    Span("Remediation: ", cls="text-xs font-bold text-accent mr-1"),
                    Span(r["remediation"], cls="text-xs text-base-content/75"),
                    cls="p-2.5 bg-black/20 rounded border border-white/5",
                ),
                cls="p-4 bg-base-200/50 rounded-lg border border-base-content/10 mb-4 last:mb-0 shadow-sm",
            )
        )

    modal_content = Div(
        close_button,
        H3("Security Rules Reference", cls="font-bold text-2xl mb-4 pr-8 text-primary"),
        Div(
            *rule_elements,
            cls="max-h-[65vh] overflow-y-auto pr-1 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/10 [&::-webkit-scrollbar-thumb]:rounded-md hover:[&::-webkit-scrollbar-thumb]:bg-white/20 [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.1)_transparent]",
        ),
        cls="modal-box w-11/12 max-w-2xl bg-base-100 shadow-[0_0_50px_0_rgba(0,0,0,0.85)] border border-secondary/20",
    )

    return Dialog(
        modal_content,
        Form(method="dialog", cls="modal-backdrop bg-black/60 backdrop-blur-sm", children=[Button("close")]),
        id=modal_id,
        cls="modal modal-bottom sm:modal-middle",
        open=True,
    )


def guild_admin_alerts_widget(guild_id: int, category: str = "all"):
    """Renders the list of security alerts filterable by a TabGroup tab bar."""
    tabs = [
        ("All", f"/dashboard/{guild_id}/alerts-list?category=all", category == "all"),
        ("Exposure", f"/dashboard/{guild_id}/alerts-list?category=exposure", category == "exposure"),
        ("Pings", f"/dashboard/{guild_id}/alerts-list?category=pings", category == "pings"),
        ("Roles", f"/dashboard/{guild_id}/alerts-list?category=roles", category == "roles"),
        ("Integrations", f"/dashboard/{guild_id}/alerts-list?category=integrations", category == "integrations"),
    ]

    with Session(engine) as session:
        evaluation = SecurityRuleEngine.evaluate(guild_id, session)
        alerts = evaluation["alerts"]
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        admin_role_configured = config and config.staff_separator_role_id is not None

    if category != "all":
        alerts = [a for a in alerts if a.get("category", "").lower() == category.lower()]

    warning_banner = ""
    if not admin_role_configured:
        warning_banner = Div(
            I(cls="fa-solid fa-triangle-exclamation text-warning mr-2 text-lg"),
            Span(
                A("Lowest Admin Role", href=f"#guild-admin-auditor-settings-{guild_id}", cls="link link-hover text-warning font-semibold"),
                " is not configured. Alerts for ",
                Span("Roles", cls="font-semibold"),
                " and ",
                Span("Pings", cls="font-semibold"),
                " categories require this setting.",
            ),
            cls="flex items-center p-3 mb-3 rounded-md border border-warning/30 bg-warning/10 text-sm",
        )

    tabs_ui = TabGroup(tabs, f"alerts-list-content-{guild_id}")
    content_id = f"alerts-list-content-{guild_id}"
    alerts_list_ui = Div(
        _render_alerts_list(alerts, guild_id),
        id=content_id,
        cls="mt-4 flex-1 min-h-0 overflow-y-auto pr-2 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/10 [&::-webkit-scrollbar-thumb]:rounded-md hover:[&::-webkit-scrollbar-thumb]:bg-white/20 [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.1)_transparent]",
    )
    color_legend = Div(
        Span("Risk Key: ", cls="text-xs font-bold opacity-70 mr-1"),
        Span("High", cls="badge badge-error badge-xs mr-1.5 font-bold px-2 py-0.5 rounded-sm"),
        Span("Med", cls="badge badge-warning badge-xs mr-1.5 font-semibold px-2 py-0.5 rounded-sm"),
        Span("Low", cls="badge badge-info badge-xs font-medium px-2 py-0.5 rounded-sm"),
        cls="flex items-center justify-center pt-2 mt-2 border-t border-white/5",
    )

    title_comp = Div(
        H3("Security Alerts", cls="card-title"),
        Button(
            I(cls="fa-solid fa-circle-info text-info fa-xl"),
            cls="btn btn-ghost btn-circle btn-md hover:opacity-100 hover:bg-white/10 transition-all",
            hx_get=f"/dashboard/{guild_id}/rules-info",
            hx_target="#modal-container",
            hx_swap="innerHTML",
            title="Rules Info",
        ),
        cls="flex justify-between items-center w-full",
    )

    return Card(
        title_comp,
        Div(
            warning_banner,
            tabs_ui,
            alerts_list_ui,
            color_legend,
            cls="flex flex-col h-full min-h-0",
        ),
        id=f"guild-admin-alerts-{guild_id}",
        cls="min-h-[480px] max-h-[640px] h-full",
    )


def guild_admin_auditor_settings_widget(guild_id: int):
    """Renders the settings card for managing auditor configurations."""
    with Session(engine) as session:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        roles = sorted(roles, key=lambda x: x.position, reverse=True)
        all_channels = session.exec(
            select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)
        ).all()

    # Reconstruct Discord-like channel hierarchy & order:
    categories = sorted([c for c in all_channels if c.type == "category"], key=lambda x: x.position)
    cat_ids = {cat.id for cat in categories}

    category_children = {}
    for c in all_channels:
        if c.type == "category":
            continue
        if c.parent_id is not None and c.parent_id in cat_ids:
            category_children.setdefault(c.parent_id, []).append(c)

    for cat_id in category_children:
        category_children[cat_id] = sorted(category_children[cat_id], key=lambda x: x.position)

    categoryless_channels = sorted(
        [c for c in all_channels if c.type != "category" and (c.parent_id is None or c.parent_id not in cat_ids)],
        key=lambda x: x.position
    )

    ordered_channels = []
    for chan in categoryless_channels:
        ordered_channels.append((chan, False))

    for cat in categories:
        ordered_channels.append((cat, True))
        for child in category_children.get(cat.id, []):
            ordered_channels.append((child, False))

    selected_role_id = config.staff_separator_role_id if config else None

    staff_ids_set = set()
    ann_ids_set = set()
    if config:
        try:
            staff_ids_set = {int(x) for x in json.loads(config.staff_channel_ids or "[]") if x is not None}
        except Exception:  # noqa: S110
            pass
        try:
            ann_ids_set = {int(x) for x in json.loads(config.announcement_channel_ids or "[]") if x is not None}
        except Exception:  # noqa: S110
            pass

    role_options = [Option("Not configured — select a role...", value="", selected=(selected_role_id is None))]
    for role in roles:
        role_options.append(Option(role.name, value=str(role.id), selected=(role.id == selected_role_id)))

    # Pre-calculate category children IDs to check if all children are checked
    cat_children_ids = {}
    for cat in categories:
        cat_children_ids[cat.id] = [child.id for child in category_children.get(cat.id, [])]

    staff_checkboxes = []
    ann_checkboxes = []
    for chan, is_cat in ordered_channels:
        if is_cat:
            # Pre-select category if its ID is explicitly in the saved list,
            # or if it has children and all children are checked.
            children_ids = cat_children_ids.get(chan.id, [])
            staff_selected = (chan.id in staff_ids_set) or (
                len(children_ids) > 0 and all(cid in staff_ids_set for cid in children_ids)
            )
            ann_selected = (chan.id in ann_ids_set) or (
                len(children_ids) > 0 and all(cid in ann_ids_set for cid in children_ids)
            )

            staff_checkboxes.append(
                Label(
                    Input(
                        type="checkbox",
                        name="staff_channel_ids",
                        value=str(chan.id),
                        checked=staff_selected,
                        cls="checkbox checkbox-primary checkbox-xs category-checkbox",
                        data_category_id=str(chan.id),
                    ),
                    Span(f" 📁 {chan.name.upper()}", cls="label-text ml-2 font-bold"),
                    cls="flex items-center p-1 rounded hover:bg-base-300 cursor-pointer text-xs channel-item font-semibold opacity-90",
                    data_name=chan.name.lower(),
                )
            )

            ann_checkboxes.append(
                Label(
                    Input(
                        type="checkbox",
                        name="announcement_channel_ids",
                        value=str(chan.id),
                        checked=ann_selected,
                        cls="checkbox checkbox-primary checkbox-xs category-checkbox",
                        data_category_id=str(chan.id),
                    ),
                    Span(f" 📁 {chan.name.upper()}", cls="label-text ml-2 font-bold"),
                    cls="flex items-center p-1 rounded hover:bg-base-300 cursor-pointer text-xs channel-item font-semibold opacity-90",
                    data_name=chan.name.lower(),
                )
            )
        else:
            staff_selected = chan.id in staff_ids_set
            ann_selected = chan.id in ann_ids_set

            parent_attrs = {}
            indent_cls = ""
            if chan.parent_id is not None and chan.parent_id in cat_ids:
                parent_attrs["data_parent_id"] = str(chan.parent_id)
                indent_cls = " pl-6"

            staff_checkboxes.append(
                Label(
                    Input(
                        type="checkbox",
                        name="staff_channel_ids",
                        value=str(chan.id),
                        checked=staff_selected,
                        cls="checkbox checkbox-primary checkbox-xs",
                        **parent_attrs,
                    ),
                    Span(f" #{chan.name}", cls="label-text ml-2 font-medium"),
                    cls=f"flex items-center p-1{indent_cls} rounded hover:bg-base-300 cursor-pointer text-xs channel-item",
                    data_name=chan.name.lower(),
                )
            )

            ann_checkboxes.append(
                Label(
                    Input(
                        type="checkbox",
                        name="announcement_channel_ids",
                        value=str(chan.id),
                        checked=ann_selected,
                        cls="checkbox checkbox-primary checkbox-xs",
                        **parent_attrs,
                    ),
                    Span(f" #{chan.name}", cls="label-text ml-2 font-medium"),
                    cls=f"flex items-center p-1{indent_cls} rounded hover:bg-base-300 cursor-pointer text-xs channel-item",
                    data_name=chan.name.lower(),
                )
            )

    tabs_nav = Div(
        Button("Admin Role", type="button", id="tab-btn-role", cls="tab tab-active transition-all duration-200 !bg-primary !text-primary-content font-extrabold shadow-md border border-primary/30", onclick="switchAuditorTab('role')"),
        Button("Staff Channels", type="button", id="tab-btn-staff", cls="tab transition-all duration-200 text-base-content/70", onclick="switchAuditorTab('staff')"),
        Button("Announcement Channels", type="button", id="tab-btn-ann", cls="tab transition-all duration-200 text-base-content/70", onclick="switchAuditorTab('ann')"),
        cls="tabs tabs-boxed mb-4 grid grid-cols-3"
    )

    panel_role = Div(
        Div(
            Div(
                Label("Lowest Admin Role", cls="label text-sm font-semibold"),
                Div(
                    I(cls="fa-solid fa-circle-info text-info opacity-60 cursor-help"),
                    cls="tooltip tooltip-right",
                    data_tip="Select the lowest role in your hierarchy that is considered admin. This role and all roles above it are treated as admin. All roles below it are non-admin and subject to security auditing.",
                ),
                cls="flex items-center gap-2",
            ),
            Select(*role_options, name="staff_separator_role_id", cls="select select-bordered w-full"),
            cls="form-control mb-4",
        ),
        id="panel-role",
        cls="tab-panel mb-4"
    )

    panel_staff = Div(
        Div(
            Div(
                Label("Staff Channels", cls="label text-sm font-semibold"),
                Div(
                    I(cls="fa-solid fa-circle-info text-info opacity-60 cursor-help"),
                    cls="tooltip tooltip-right",
                    data_tip="Select Discord channels that are considered staff-only. The auditor checks whether non-staff roles can view these channels.",
                ),
                cls="flex items-center gap-2",
            ),
            Input(
                type="text",
                placeholder="Search staff channels...",
                cls="input input-bordered input-xs w-full mb-2",
                oninput="const q = this.value.toLowerCase(); document.getElementById('staff-channels-list').querySelectorAll('.channel-item').forEach(el => { el.style.display = el.getAttribute('data-name').includes(q) ? 'flex' : 'none'; })",
            ),
            Div(
                *staff_checkboxes,
                id="staff-channels-list",
                cls="flex-1 min-h-0 overflow-y-auto border border-base-300 rounded-md p-2 space-y-1 bg-base-200/50 channels-list",
            ),
            cls="form-control mb-4 h-full min-h-0 flex flex-col",
        ),
        id="panel-staff",
        cls="tab-panel hidden mb-4 h-full min-h-0 flex flex-col"
    )

    panel_ann = Div(
        Div(
            Div(
                Label("Announcement Channels", cls="label text-sm font-semibold"),
                Div(
                    I(cls="fa-solid fa-circle-info text-info opacity-60 cursor-help"),
                    cls="tooltip tooltip-right",
                    data_tip="Select Discord channels designated for announcements. The auditor checks whether non-staff roles can send messages or mention everyone in these channels.",
                ),
                cls="flex items-center gap-2",
            ),
            Input(
                type="text",
                placeholder="Search announcement channels...",
                cls="input input-bordered input-xs w-full mb-2",
                oninput="const q = this.value.toLowerCase(); document.getElementById('ann-channels-list').querySelectorAll('.channel-item').forEach(el => { el.style.display = el.getAttribute('data-name').includes(q) ? 'flex' : 'none'; })",
            ),
            Div(
                *ann_checkboxes,
                id="ann-channels-list",
                cls="flex-1 min-h-0 overflow-y-auto border border-base-300 rounded-md p-2 space-y-1 bg-base-200/50 channels-list",
            ),
            cls="form-control mb-4 h-full min-h-0 flex flex-col",
        ),
        id="panel-ann",
        cls="tab-panel hidden mb-4 h-full min-h-0 flex flex-col"
    )

    form_content = Form(
        tabs_nav,
        panel_role,
        panel_staff,
        panel_ann,
        Button("Save Settings", type="submit", cls="btn btn-primary w-full mt-auto"),
        Script("""
if (!window.auditorSettingsInitialized) {
    window.auditorSettingsInitialized = true;

    window.switchAuditorTab = function(tabName) {
        const panels = ['role', 'staff', 'ann'];
        panels.forEach(name => {
            const panel = document.getElementById('panel-' + name);
            if (panel) panel.classList.add('hidden');

            const btn = document.getElementById('tab-btn-' + name);
            if (btn) {
                btn.classList.remove('tab-active', '!bg-primary', '!text-primary-content', 'font-extrabold', 'shadow-md', 'border', 'border-primary/30');
                btn.classList.add('text-base-content/70');
            }
        });

        const activePanel = document.getElementById('panel-' + tabName);
        if (activePanel) activePanel.classList.remove('hidden');

        const activeBtn = document.getElementById('tab-btn-' + tabName);
        if (activeBtn) {
            activeBtn.classList.remove('text-base-content/70');
            activeBtn.classList.add('tab-active', '!bg-primary', '!text-primary-content', 'font-extrabold', 'shadow-md', 'border', 'border-primary/30');
        }

        localStorage.setItem('activeAuditorTab', tabName);
    };

    document.addEventListener('change', function(e) {
        if (!e.target) return;
        if (e.target.classList.contains('category-checkbox')) {
            const catId = e.target.getAttribute('data-category-id');
            const checked = e.target.checked;
            const container = e.target.closest('.channels-list');
            if (container) {
                container.querySelectorAll('input[data-parent-id="' + catId + '"]').forEach(el => {
                    el.checked = checked;
                });
            }
        } else if (e.target.hasAttribute('data-parent-id')) {
            const parentId = e.target.getAttribute('data-parent-id');
            const container = e.target.closest('.channels-list');
            if (container) {
                const catCheckbox = container.querySelector('input[data-category-id="' + parentId + '"]');
                if (catCheckbox) {
                    const siblings = container.querySelectorAll('input[data-parent-id="' + parentId + '"]');
                    const allChecked = Array.from(siblings).every(el => el.checked);
                    catCheckbox.checked = allChecked;
                }
            }
        }
    });
}

(function() {
    const savedTab = localStorage.getItem('activeAuditorTab') || 'role';
    window.switchAuditorTab(savedTab);
})();
        """),
        hx_post=f"/dashboard/{guild_id}/auditor-settings",
        hx_target=f"#guild-admin-auditor-settings-{guild_id}",
        cls="flex flex-col h-full min-h-0",
    )

    return Card("Auditor Settings", form_content, id=f"guild-admin-auditor-settings-{guild_id}", cls="min-h-[480px] max-h-[800px] h-full")


def _render_utilities_sidebar(guild_id: int, session: Optional[Session] = None) -> FT:
    if session is None:
        with Session(engine) as session:
            return _render_utilities_sidebar_inner(guild_id, session)
    return _render_utilities_sidebar_inner(guild_id, session)


def _render_utilities_sidebar_inner(guild_id: int, session: Session) -> FT:
    evaluation = SecurityRuleEngine.evaluate(guild_id, session)
    score = evaluation["score"]
    if score >= 80:
        score_color = "text-success"
    elif score >= 50:
        score_color = "text-warning"
    else:
        score_color = "text-error"

    roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
    channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()

    admin_roles = sum(1 for r in roles if (r.permissions & (1 << 3)) and not r.is_managed)
    private_channels_count = 0
    for c in channels:
        if c.overwrites:
            try:
                ov = json.loads(c.overwrites)
                everyone_ov = ov.get(str(guild_id))
                if everyone_ov and (everyone_ov.get("deny", 0) & (1 << 10)):
                    private_channels_count += 1
            except (json.JSONDecodeError, TypeError):
                pass

    return Card(
        "Utilities Sidebar",
        Div(
            Div(
                Span("Security Health Score: ", cls="font-semibold text-sm"),
                Span(f"{score}/100", cls=f"font-bold text-lg {score_color}"),
                cls="mb-3",
            ),
            Div(
                Div(f"Roles: {len(roles)} ({admin_roles} Admin)", cls="text-xs opacity-80"),
                Div(f"Channels: {len(channels)} ({private_channels_count} Private)", cls="text-xs opacity-80"),
                cls="mb-4 bg-base-200/50 p-2 rounded-md",
            ),
            Div(
                H4("Quick Navigation", cls="font-semibold text-sm mb-2"),
                Ul(
                    Li(
                        A(
                            "Security Overview",
                            href=f"#guild-admin-security-overview-{guild_id}",
                            cls="link link-hover text-xs",
                        )
                    ),
                    Li(A("Security Alerts", href=f"#guild-admin-alerts-{guild_id}", cls="link link-hover text-xs")),
                    Li(
                        A(
                            "Alert Overrides",
                            href=f"#guild-admin-security-overrides-{guild_id}",
                            cls="link link-hover text-xs",
                        )
                    ),
                    Li(A("Guild Roles", href=f"#guild-admin-audit-roles-{guild_id}", cls="link link-hover text-xs")),
                    Li(
                        A(
                            "Guild Channels",
                            href=f"#guild-admin-audit-channels-{guild_id}",
                            cls="link link-hover text-xs",
                        )
                    ),
                    Li(
                        A(
                            "Permissions Matrix",
                            href=f"#guild-admin-audit-permissions-{guild_id}",
                            cls="link link-hover text-xs",
                        )
                    ),
                    Li(
                        A(
                            "Auditor Settings",
                            href=f"#guild-admin-auditor-settings-{guild_id}",
                            cls="link link-hover text-xs",
                        )
                    ),
                    cls="space-y-1 list-none p-0",
                ),
                cls="mb-4",
            ),
            Button(
                "Run Security Scan",
                hx_post=f"/dashboard/{guild_id}/scan",
                hx_target=f"#guild-admin-utilities-sidebar-{guild_id}",
                hx_swap="outerHTML",
                cls="btn btn-primary btn-sm w-full",
            ),
        ),
        id=f"guild-admin-utilities-sidebar-{guild_id}",
        cls="h-full",
    )


def guild_admin_utilities_sidebar(guild_id: int, session: Optional[Session] = None) -> FT:
    return _render_utilities_sidebar(guild_id, session)


guild_admin_utilities_sidebar.position_config = "left"


def _render_utilities_help_bubble(guild_id: int, session: Optional[Session] = None) -> FT:
    help_icon_svg = NotStr(
        '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 5.25h.008v.008H12v-.008Z" />'
        "</svg>"
    )
    close_icon_svg = NotStr(
        '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />'
        "</svg>"
    )

    card_content = Div(
        # Header with close button
        Div(
            H3("Utilities Help", cls="text-sm font-bold text-primary flex items-center gap-1.5"),
            Button(
                close_icon_svg,
                cls="btn btn-ghost btn-xs btn-circle text-base-content/70 hover:text-base-content",
                onclick=f"document.getElementById('help-bubble-card-{guild_id}').classList.add('hidden')",
            ),
            cls="flex justify-between items-center border-b border-white/10 pb-2 mb-3",
        ),
        # Slash Commands
        Div(
            H4("Slash Commands", cls="font-semibold text-xs mb-1.5 opacity-80 text-secondary"),
            Ul(
                Li(Code("/audit run"), " - Triggers permission auditor.", cls="text-xs mb-1 list-none"),
                Li(Code("/audit config get"), " - Displays config.", cls="text-xs mb-1 list-none"),
                Li(Code("/audit config set"), " - Updates config.", cls="text-xs mb-1 list-none"),
                cls="p-0 space-y-1",
            ),
            cls="mb-4",
        ),
        # Bot Connection Status
        Div(
            H4("Bot Connection Status", cls="font-semibold text-xs mb-2 opacity-80 text-secondary"),
            Div(
                Span("Status: ", cls="text-xs font-semibold mr-1"),
                Span(
                    "🔴 Disconnected",
                    id=f"bot-latency-display-{guild_id}",
                    hx_get=f"/dashboard/{guild_id}/ping-bot",
                    hx_trigger="load",
                    hx_swap="outerHTML",
                    cls="badge badge-error badge-sm text-error-content",
                ),
                cls="mb-3 flex items-center",
            ),
            Button(
                "Test Connection",
                hx_get=f"/dashboard/{guild_id}/ping-bot",
                hx_target=f"#bot-latency-display-{guild_id}",
                hx_swap="outerHTML",
                cls="btn btn-outline btn-xs btn-primary w-full",
            ),
        ),
        id=f"help-bubble-card-{guild_id}",
        cls="hidden absolute bottom-16 right-0 w-80 bg-neutral/95 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl p-4 z-50 text-left",
    )

    toggle_btn = Button(
        help_icon_svg,
        onclick=f"document.getElementById('help-bubble-card-{guild_id}').classList.toggle('hidden')",
        cls="btn btn-circle btn-lg text-primary hover:text-secondary shadow-lg hover:scale-110 active:scale-95 transition-all duration-200",
        style="border-radius: 50% !important; background-color: hsl(var(--n) / 0.8) !important; backdrop-filter: blur(8px) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important;",
    )

    return Div(card_content, toggle_btn, id=f"guild-admin-utilities-help-bubble-{guild_id}", cls="relative")


def guild_admin_utilities_help_bubble(guild_id: int, session: Optional[Session] = None) -> FT:
    return _render_utilities_help_bubble(guild_id, session)


guild_admin_utilities_help_bubble.position_config = "bottom-right"


def get_override_confirm_modal_html(guild_id: int, alert_hash: str) -> FT:
    with Session(engine) as session:
        evaluation = SecurityRuleEngine.evaluate(guild_id, session, include_overridden=True)
        alerts = evaluation["alerts"]
        alert = next((a for a in alerts if a.get("alert_hash") == alert_hash), None)

    if not alert:
        modal_content = Div(
            Form(
                Button(I(cls="fa-solid fa-xmark"), cls="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"),
                method="dialog",
            ),
            H3("Alert Not Found", cls="font-bold text-lg text-error mb-4"),
            P("The selected alert could not be found or has already been overridden.", cls="text-sm opacity-80"),
            cls="modal-box bg-base-100 border border-error/20 shadow-2xl",
        )
        return Dialog(
            modal_content,
            Form(method="dialog", cls="modal-backdrop", children=[Button("close")]),
            id="modal-override-confirm",
            cls="modal modal-bottom sm:modal-middle",
            open=True,
        )

    modal_content = Div(
        Form(
            Button(I(cls="fa-solid fa-xmark"), cls="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"),
            method="dialog",
        ),
        H3("Confirm Alert Override", cls="font-bold text-xl text-warning mb-4"),
        P("You are overriding the following security alert:", cls="text-sm opacity-70 mb-2"),
        Div(
            Div(
                Span(alert["rule"], cls="badge badge-warning badge-sm font-bold mr-2"),
                Span(alert["category"].upper(), cls="text-[10px] opacity-50 uppercase font-semibold"),
                cls="flex items-center mb-1",
            ),
            P(alert["message"], cls="text-sm font-medium mb-1"),
            P(alert.get("details", ""), cls="text-xs opacity-60 mb-2") if alert.get("details") else "",
            cls="p-3 bg-base-200/50 rounded-md border border-white/5 mb-4",
        ),
        Form(
            Input(type="hidden", name="alert_hash", value=alert_hash),
            Input(type="hidden", name="rule", value=alert["rule"]),
            Input(type="hidden", name="category", value=alert["category"]),
            Input(type="hidden", name="message", value=alert["message"]),
            Input(type="hidden", name="details", value=alert.get("details", "")),
            Div(
                Label("Optional Comment / Reason for Override", cls="label text-sm font-semibold mb-1"),
                Textarea(
                    name="comment",
                    placeholder="e.g. Approved exception for dev channel...",
                    cls="textarea textarea-bordered w-full h-24 text-sm bg-base-200/50",
                ),
                cls="form-control mb-4",
            ),
            Div(
                Button(
                    "Cancel",
                    type="button",
                    cls="btn btn-ghost mr-2",
                    onclick="document.getElementById('modal-override-confirm').close()",
                ),
                Button("Override Alert", type="submit", cls="btn btn-warning"),
                cls="flex justify-end w-full",
            ),
            hx_post=f"/dashboard/{guild_id}/alerts/override",
            hx_target="#modal-container",
        ),
        cls="modal-box bg-base-100 border border-warning/20 shadow-2xl w-11/12 max-w-lg",
    )

    return Dialog(
        modal_content,
        Form(method="dialog", cls="modal-backdrop", children=[Button("close")]),
        id="modal-override-confirm",
        cls="modal modal-bottom sm:modal-middle",
        open=True,
    )


def guild_admin_security_overrides_widget(guild_id: int):
    """Displays overridden security alerts with option to remove override."""
    with Session(engine) as session:
        overrides = session.exec(select(SecurityAlertOverride).where(SecurityAlertOverride.guild_id == guild_id)).all()

    if not overrides:
        return Card(
            "Security Alert Overrides",
            Div("No overrides currently configured.", cls="opacity-70 text-sm mt-2"),
            id=f"guild-admin-security-overrides-{guild_id}",
        )

    override_rows = []
    for o in overrides:
        override_rows.append(
            Div(
                Div(
                    Div(
                        Span(o.rule, cls="font-bold text-sm text-secondary"),
                        Span(o.category.upper(), cls="text-[10px] opacity-50 uppercase font-semibold ml-2"),
                        cls="flex items-center mb-1",
                    ),
                    P(o.message, cls="text-sm font-medium mb-1"),
                    Div(
                        Span("Comment: ", cls="text-xs font-bold text-accent mr-1"),
                        Span(o.comment or "No comment provided", cls="text-xs text-base-content/75 italic"),
                        cls="p-2 bg-black/20 rounded border border-white/5 mt-1",
                    )
                    if o.comment
                    else "",
                    cls="flex-1",
                ),
                Div(
                    Button(
                        "Remove Override",
                        hx_post=f"/dashboard/{guild_id}/alerts/override/remove?alert_hash={o.alert_hash}",
                        cls="btn btn-xs btn-outline btn-error whitespace-nowrap",
                    ),
                    cls="flex items-center ml-4",
                ),
                cls="p-3 bg-base-200/50 rounded-md border border-white/10 flex justify-between items-start mb-3 last:mb-0",
            )
        )

    return Card(
        "Security Alert Overrides",
        Div(*override_rows),
        id=f"guild-admin-security-overrides-{guild_id}",
    )
