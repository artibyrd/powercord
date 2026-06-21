# mypy: ignore-errors
import json
import logging
import re
from typing import Optional

from cachetools import TTLCache
from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.common.discord_constants import ALL_PERMISSIONS, OTHER_PERMISSIONS, SENSITIVE_PERMISSIONS
from app.db.models import DiscordAuditorConfig, DiscordChannel, DiscordRole, GuildExtensionSettings
from app.ui.components import (
    Accordion,
    AlertsGauge,
    Card,
    HealthScoreArc,
    ProgressBarStat,
    SegmentedDigit,
    TabGroup,
)

engine = init_connection_engine()


def _get_common_legend(for_roles=False):
    items = []
    if for_roles:
        items.append(
            Li(
                Span("✅/❌: ", cls="font-bold"),
                "Indicates if a role is Hoisted (displayed separately) or Managed (by an integration).",
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
            Span("Admin", cls="badge badge-neutral badge-sm px-2 rounded-md mr-1 mb-1 font-bold", title="Administrator")
        )

    # Manager (Manage Server, Manage Roles, Manage Channels)
    if permissions & (1 << 5) or permissions & (1 << 28) or permissions & (1 << 4):
        badges.append(
            Span(
                "Manager",
                cls="badge badge-ghost badge-sm px-2 rounded-md mr-1 mb-1",
                title="Manage Server/Roles/Channels",
            )
        )

    # Moderator (Kick, Ban)
    if permissions & (1 << 1) or permissions & (1 << 2):
        badges.append(Span("Mod", cls="badge badge-ghost badge-sm px-2 rounded-md mr-1 mb-1", title="Kick/Ban Members"))

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
                detailed_perms.append(
                    Span(
                        perm_name,
                        cls="inline-flex justify-center items-center px-1.5 py-0.5 rounded text-[10px] font-medium border border-base-content/10 bg-base-200 text-base-content/70 w-full",
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
            Div("Hoist", cls="col-span-1 font-bold text-center"),
            Div("Bot", cls="col-span-1 font-bold text-center"),
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
                            color_cls = "badge-ghost bg-base-200 border-base-300 text-base-content"
                        elif deny_count > 0:
                            color_cls = "badge-neutral"
                        elif allow_count > 0:
                            color_cls = "badge-ghost"  # Mixed

                        # Build specific permissions UI for this target
                        target_detailed_perms = []
                        for perm_name, perm_value in ALL_PERMISSIONS.items():
                            if allow_val & perm_value:
                                target_detailed_perms.append(
                                    Span(
                                        perm_name,
                                        cls="inline-flex justify-center items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-base-200 text-base-content/80 border border-base-content/10 w-full",
                                    )
                                )
                            elif deny_val & perm_value:
                                target_detailed_perms.append(
                                    Span(
                                        perm_name,
                                        cls="inline-flex justify-center items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-neutral/20 text-neutral-content/80 border border-neutral/30 w-full",
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
    alert_pct = min(100, len(alerts) * 10)  # Each alert = 10%, capped at 100%

    gauges_row = Div(
        HealthScoreArc(score, len(alerts)),
        AlertsGauge(alert_pct, len(alerts)),
        cls="flex justify-around items-center w-full mb-1",
    )

    stats_grid = Div(
        Div(
            ProgressBarStat("Total Roles", len(roles), DISCORD_MAX_ROLES),
            ProgressBarStat("Total Channels", len(channels), DISCORD_MAX_CHANNELS),
            cls="grid grid-cols-2 gap-3 w-full",
        ),
        Div(
            SegmentedDigit(admin_roles_count, "Admin Roles", "text-error"),
            SegmentedDigit(private_channels_count, "Private Channels", "text-info"),
            cls="grid grid-cols-2 gap-3 w-full",
        ),
        cls="flex flex-col gap-3 w-full flex-1",
    )

    return Card(
        "Security Overview",
        Div(
            gauges_row,
            stats_grid,
            cls="flex flex-col gap-4 items-center w-full h-full",
        ),
        id=f"guild-admin-security-overview-{guild_id}",
        cls="min-h-[360px] h-full",
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
                    badge = Span(
                        role.name,
                        cls="inline-flex items-center px-2 py-0.5 rounded-md mr-1 mb-1 text-xs font-medium border border-base-content/10 bg-base-200 text-base-content/80",
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

    return Accordion(
        "Permissions Matrix",
        Div(
            P(
                "Overview indicating which roles currently possess sensitive administrative or moderation permissions.",
                cls="text-xs opacity-70 mb-2",
            ),
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
                            "details": f"Target {display_name} has less restricted overwrites. Leaked allows: {decode_permissions(leaked_allows)}, leaked denies: {decode_permissions(leaked_denies)}.",
                            "action_buttons": [],
                        }
                    )
        return alerts


def get_effective_channel_permissions(
    role: DiscordRole, channel: DiscordChannel, everyone_role: Optional[DiscordRole], overwrites: dict
) -> int:
    base_everyone = everyone_role.permissions if everyone_role else 0
    if role.position == 0 or (everyone_role and role.id == everyone_role.id):
        ev_ov = overwrites.get(str(role.id), {})
        allow_ev = ev_ov.get("allow", 0)
        deny_ev = ev_ov.get("deny", 0)
        p = (base_everyone & ~deny_ev) | allow_ev
        if p & (1 << 3):  # Administrator
            return 0xFFFFFFFFFFFFFFFF
        return p

    base_role = role.permissions | base_everyone
    ev_id = str(everyone_role.id) if everyone_role else str(role.guild_id)
    ev_ov = overwrites.get(ev_id, {})
    allow_ev = ev_ov.get("allow", 0)
    deny_ev = ev_ov.get("deny", 0)

    p = (base_role & ~deny_ev) | allow_ev

    role_ov = overwrites.get(str(role.id), {})
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
        alerts = []

        for c in channels:
            if c.type == "category":
                continue
            is_ann = (c.id in ann_channel_ids) or ("announcement" in c.name.lower()) or ("rules" in c.name.lower())
            if not is_ann:
                continue

            try:
                overwrites = json.loads(c.overwrites or "{}")
            except Exception:  # noqa: S112
                continue

            for r in roles:
                is_everyone = r.position == 0 or r.id == guild_id
                is_below_sep = sep_pos is not None and r.position < sep_pos
                if is_everyone or is_below_sep:
                    p = get_effective_channel_permissions(r, c, everyone_role, overwrites)
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
            is_staff = (c.id in staff_channel_ids) or any(k in c.name.lower() for k in ["staff", "admin", "moderator"])
            if not is_staff:
                continue

            try:
                overwrites = json.loads(c.overwrites or "{}")
            except Exception:
                overwrites = {}

            # Inherit parent overwrites
            parent = categories.get(c.parent_id) if c.parent_id else None
            if parent:
                try:
                    parent_ov = json.loads(parent.overwrites or "{}")
                except Exception:
                    parent_ov = {}
                effective_overwrites = dict(parent_ov)
                effective_overwrites.update(overwrites)
            else:
                effective_overwrites = overwrites

            for r in non_staff_roles:
                # Compute View Channel permission access
                if r.position == 0 or r.id == guild_id:
                    everyone_ov = effective_overwrites.get(str(r.id), {})
                    has_view = (everyone_ov.get("deny", 0) & (1 << 10)) == 0
                else:
                    r_ov = effective_overwrites.get(str(r.id), {})
                    everyone_ov = effective_overwrites.get(str(guild_id), {})
                    everyone_denied = (everyone_ov.get("deny", 0) & (1 << 10)) != 0

                    has_view = (
                        bool(r.permissions & (1 << 3))
                        or bool(r_ov.get("allow", 0) & (1 << 10))
                        or (not everyone_denied and (r_ov.get("deny", 0) & (1 << 10)) == 0)
                    )

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
        alerts = []

        for c in channels:
            if not any(k in c.type.lower() for k in ["voice", "thread", "forum"]):
                continue

            try:
                overwrites = json.loads(c.overwrites or "{}")
            except Exception:  # noqa: S112
                continue

            for r in roles:
                is_everyone = r.position == 0 or r.id == guild_id
                is_below_sep = sep_pos is not None and r.position < sep_pos
                if is_everyone or is_below_sep:
                    p = get_effective_channel_permissions(r, c, everyone_role, overwrites)
                    if (p & (1 << 11)) or (p & (1 << 17)) or (r.permissions & (1 << 3)):
                        alerts.append(
                            {
                                "rule": self.name,
                                "category": self.category,
                                "severity": self.severity,
                                "message": f"Non-text location #{c.name} allows role '{r.name}' to send messages or mention everyone.",
                                "details": f"Channel of type '{c.type}' allows role '{r.name}' below staff separator to Send Messages or Mention Everyone. Allowed permissions: {decode_permissions(p)}.",
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
                        "details": f"Role '{r.name}' below staff separator is set to mentionable, posing a mass ping raid vulnerability.",
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
                protected_ids = set(
                    session.exec(select(HoneypotChannel.channel_id).where(HoneypotChannel.guild_id == guild_id)).all()
                )
            except Exception:  # noqa: S110
                pass

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


class SecurityRuleEngine:
    _evaluation_cache: TTLCache = TTLCache(maxsize=256, ttl=120)

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
    def evaluate(guild_id: int, session: Session) -> dict:
        guild_id = int(guild_id)
        if guild_id in SecurityRuleEngine._evaluation_cache:
            return SecurityRuleEngine._evaluation_cache[guild_id]
        res = SecurityRuleEngine().run_all(guild_id, session)
        SecurityRuleEngine._evaluation_cache[guild_id] = res
        return res

    def run_all(self, guild_id: int, session: Session) -> dict:
        alerts = []
        for rule in self.rules:
            try:
                rule_alerts = rule.evaluate(guild_id, session)
                alerts.extend(rule_alerts)
            except Exception as e:
                logging.exception(f"Error evaluating rule {rule.name}: {e}")

        score = 100
        for alert in alerts:
            sev = alert.get("severity", "").lower()
            if sev == "high":
                score -= 15
            elif sev == "medium":
                score -= 10
            elif sev == "low":
                score -= 5

        score = max(0, score)
        return {"score": score, "alerts": alerts}


def format_details(details: str) -> FT:
    if not details:
        return ""

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

    def make_perm_badge(p_name: str) -> FT:
        p_clean = p_name.strip("' ")
        if p_clean.lower() == "none":
            return Span("None", cls="text-xs opacity-50 font-mono")
        if p_clean in high_risk_perms:
            return Span(p_clean, cls="badge badge-error badge-outline badge-xs mr-1 mb-1 font-bold shadow-sm")
        elif p_clean in medium_risk_perms:
            return Span(p_clean, cls="badge badge-warning badge-outline badge-xs mr-1 mb-1 font-semibold")
        else:
            return Span(p_clean, cls="badge badge-info badge-outline badge-xs mr-1 mb-1 font-medium")

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
                Span("Leaked Allows: ", cls="text-xs font-bold opacity-75 mr-2"),
                Div(*allows_badges, cls="inline-flex flex-wrap items-center"),
                cls="mb-1.5 flex flex-wrap items-center",
            ),
            Div(
                Span("Leaked Denies: ", cls="text-xs font-bold opacity-75 mr-2"),
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
                Span("Permissions: ", cls="text-xs font-bold opacity-75 mr-2"),
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


def _render_alerts_list(alerts: list[dict]) -> FT:
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

        alert_elements.append(
            Div(
                Div(
                    Span(alert.get("rule", "Security Alert"), cls=f"badge {badge_cls} badge-sm mr-2 font-bold"),
                    Span(alert.get("category", "").upper(), cls="text-[10px] opacity-50 uppercase font-semibold"),
                    cls="flex items-center mb-1",
                ),
                P(alert.get("message", ""), cls="text-sm font-medium mb-1"),
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
                Div(*buttons, cls="flex") if buttons else "",
                cls=f"p-3 rounded-md border-l-4 border {border_cls} mb-3 last:mb-0",
            )
        )
    return Div(*alert_elements)


def guild_admin_alerts_widget(guild_id: int, category: str = "all"):
    """Renders the list of security alerts filterable by a TabGroup tab bar."""
    tabs = [
        ("All", f"/dashboard/{guild_id}/alerts-list?category=all", category == "all"),
        ("Exposure", f"/dashboard/{guild_id}/alerts-list?category=exposure", category == "exposure"),
        ("Pings", f"/dashboard/{guild_id}/alerts-list?category=pings", category == "pings"),
        ("Roles", f"/dashboard/{guild_id}/alerts-list?category=roles", category == "roles"),
    ]

    with Session(engine) as session:
        evaluation = SecurityRuleEngine.evaluate(guild_id, session)
        alerts = evaluation["alerts"]

    if category != "all":
        alerts = [a for a in alerts if a.get("category", "").lower() == category.lower()]

    tabs_ui = TabGroup(tabs, f"alerts-list-content-{guild_id}")
    content_id = f"alerts-list-content-{guild_id}"
    alerts_list_ui = Div(
        _render_alerts_list(alerts),
        id=content_id,
        cls="mt-4 flex-1 min-h-0 overflow-y-auto pr-2 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/10 [&::-webkit-scrollbar-thumb]:rounded-md hover:[&::-webkit-scrollbar-thumb]:bg-white/20 [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.1)_transparent]",
    )
    color_legend = Div(
        Span("Risk Key: ", cls="text-xs font-bold opacity-70 mr-1"),
        Span("High", cls="badge badge-error badge-xs mr-1.5 font-bold px-1.5 rounded-sm"),
        Span("Med", cls="badge badge-warning badge-xs mr-1.5 font-semibold px-1.5 rounded-sm"),
        Span("Low", cls="badge badge-info badge-xs font-medium px-1.5 rounded-sm"),
        cls="flex items-center justify-center pt-2 mt-2 border-t border-white/5",
    )

    return Card(
        "Security Alerts",
        Div(
            tabs_ui,
            alerts_list_ui,
            color_legend,
            cls="flex flex-col h-full",
        ),
        id=f"guild-admin-alerts-{guild_id}",
        cls="min-h-[360px] h-full",
    )


def guild_admin_auditor_settings_widget(guild_id: int):
    """Renders the settings card for managing auditor configurations."""
    with Session(engine) as session:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        roles = sorted(roles, key=lambda x: x.position, reverse=True)

    selected_role_id = config.staff_separator_role_id if config else None

    staff_ids_list = []
    ann_ids_list = []
    if config:
        try:
            staff_ids_list = json.loads(config.staff_channel_ids or "[]")
        except Exception:  # noqa: S110
            pass
        try:
            ann_ids_list = json.loads(config.announcement_channel_ids or "[]")
        except Exception:  # noqa: S110
            pass

    staff_ids_str = ", ".join(str(x) for x in staff_ids_list)
    ann_ids_str = ", ".join(str(x) for x in ann_ids_list)

    role_options = [Option("None / Select a role...", value="", selected=(selected_role_id is None))]
    for role in roles:
        role_options.append(Option(role.name, value=str(role.id), selected=(role.id == selected_role_id)))

    form_content = Form(
        Div(
            Div(
                Label("Staff Separator Role", cls="label text-sm font-semibold"),
                Div(
                    I(cls="fa-solid fa-circle-info text-info opacity-60 cursor-help"),
                    cls="tooltip tooltip-right",
                    data_tip='The role that divides staff from community members in the role hierarchy. Roles below this position are treated as "non-staff" by the security auditor.',
                ),
                cls="flex items-center gap-2",
            ),
            Select(*role_options, name="staff_separator_role_id", cls="select select-bordered w-full"),
            cls="form-control mb-4",
        ),
        Div(
            Div(
                Label("Staff Channel IDs", cls="label text-sm font-semibold"),
                Div(
                    I(cls="fa-solid fa-circle-info text-info opacity-60 cursor-help"),
                    cls="tooltip tooltip-right",
                    data_tip="Comma-separated Discord channel IDs that are considered staff-only. The auditor checks whether non-staff roles can view these channels.",
                ),
                cls="flex items-center gap-2",
            ),
            Input(
                type="text",
                name="staff_channel_ids",
                value=staff_ids_str,
                placeholder="e.g. 1234567890, 0987654321",
                cls="input input-bordered w-full",
            ),
            cls="form-control mb-4",
        ),
        Div(
            Div(
                Label("Announcement Channel IDs", cls="label text-sm font-semibold"),
                Div(
                    I(cls="fa-solid fa-circle-info text-info opacity-60 cursor-help"),
                    cls="tooltip tooltip-right",
                    data_tip="Comma-separated Discord channel IDs designated for announcements. The auditor checks whether non-staff roles can send messages or mention everyone in these channels.",
                ),
                cls="flex items-center gap-2",
            ),
            Input(
                type="text",
                name="announcement_channel_ids",
                value=ann_ids_str,
                placeholder="e.g. 1234567890, 0987654321",
                cls="input input-bordered w-full",
            ),
            cls="form-control mb-4",
        ),
        Button("Save Settings", type="submit", cls="btn btn-primary w-full"),
        hx_post=f"/dashboard/{guild_id}/auditor-settings",
        hx_target=f"#guild-admin-auditor-settings-{guild_id}",
    )

    return Card("Auditor Settings", form_content, id=f"guild-admin-auditor-settings-{guild_id}")


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
                            "Auditor Settings",
                            href=f"#guild-admin-auditor-settings-{guild_id}",
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
