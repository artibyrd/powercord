# mypy: ignore-errors
import json
import logging

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.common.discord_constants import ALL_PERMISSIONS, OTHER_PERMISSIONS, SENSITIVE_PERMISSIONS
from app.db.models import DiscordChannel, DiscordRole
from app.ui.components import Card

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
            Span("Admin", cls="badge badge-error badge-sm px-2 rounded-md mr-1 mb-1 font-bold", title="Administrator")
        )

    # Manager (Manage Server, Manage Roles, Manage Channels)
    if permissions & (1 << 5) or permissions & (1 << 28) or permissions & (1 << 4):
        badges.append(
            Span(
                "Manager",
                cls="badge badge-warning badge-sm px-2 rounded-md mr-1 mb-1",
                title="Manage Server/Roles/Channels",
            )
        )

    # Moderator (Kick, Ban)
    if permissions & (1 << 1) or permissions & (1 << 2):
        badges.append(Span("Mod", cls="badge badge-info badge-sm px-2 rounded-md mr-1 mb-1", title="Kick/Ban Members"))

    return badges


def guild_admin_audit_roles_widget(guild_id: int):
    """Displays Discord server roles for a specific guild.

    Fetches the roles stored by the `utilities` audit command and renders them
    in a detailed FastHTML table with color indicators and permission badges.
    """
    with Session(engine) as session:
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()

    if not roles:
        return Card("Start Audit to view Roles", Div("No roles found for this server.", cls="opacity-70 text-sm mt-2"))

    roles = sorted(roles, key=lambda x: x.position, reverse=True)

    role_rows = []
    for role in roles:
        badges = _get_role_badges(role.permissions)

        # Build detailed permissions badges
        detailed_perms = []
        for perm_name, perm_value in ALL_PERMISSIONS.items():
            if bool(role.permissions & perm_value) or bool(role.permissions & (1 << 3)):
                color_css = ""
                if role.color:
                    hex_str = f"{role.color:06x}"
                    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                    text_color = "#000000" if luminance > 0.5 else "#ffffff"
                    color_css = f"background-color: #{hex_str}; color: {text_color}; border-color: #{hex_str};"
                detailed_perms.append(
                    Span(
                        perm_name,
                        cls="inline-flex justify-center items-center px-1.5 py-0.5 rounded text-[10px] font-medium border border-base-content/10 w-full",
                        style=color_css,
                    )
                )

        if detailed_perms:
            perms_ui = Div(*detailed_perms, cls="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2 mt-2")
        else:
            perms_ui = Div(Span("No explicit permissions", cls="opacity-50 text-xs italic"), cls="mt-2")

        # The row header (summary) mimics the table headers exactly
        role_summary_ui = Summary(
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
            cls="grid grid-cols-12 gap-2 px-4 py-3 hover:bg-base-200/50 transition-colors cursor-pointer list-none items-center",
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

    return Card(
        "Guild Roles", Div(_get_common_legend(for_roles=True), guild_section), id=f"guild-admin-audit-roles-{guild_id}"
    )


def guild_admin_audit_channels_widget(guild_id: int):
    """Displays Discord server channels for a specific guild.

    Groups channels by their parent category and visually indicates inherited
    versus explicit permission overwrites using FastHTML components.
    """
    with Session(engine) as session:
        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()

    if not channels:
        return Card(
            "Start Audit to view Channels", Div("No channels found for this server.", cls="opacity-70 text-sm mt-2")
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
                            color_cls = "badge-success text-success-content border-success"
                        elif deny_count > 0:
                            color_cls = "badge-error text-error-content border-error"
                        elif allow_count > 0:
                            color_cls = "badge-warning border-warning"  # Mixed

                        # Build specific permissions UI for this target
                        target_detailed_perms = []
                        for perm_name, perm_value in ALL_PERMISSIONS.items():
                            if allow_val & perm_value:
                                target_detailed_perms.append(
                                    Span(
                                        perm_name,
                                        cls="inline-flex justify-center items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-success/20 text-success border border-success/30 w-full hover:bg-success/30 transition-colors",
                                    )
                                )
                            elif deny_val & perm_value:
                                target_detailed_perms.append(
                                    Span(
                                        perm_name,
                                        cls="inline-flex justify-center items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-error/20 text-error border border-error/30 w-full hover:bg-error/30 transition-colors",
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
                    Span("▶", cls="text-[8px] opacity-40 mr-2 group-open:rotate-90 transition-transform inline-block"),
                    icon,
                    Span(chan.name, cls=f"ml-2 {name_cls}"),
                    cls="col-span-5 flex items-center",
                    style=f"padding-left: {indent}em",
                ),
                Div(overwrites_ui, cls="col-span-7"),
                cls="grid grid-cols-12 gap-2 px-4 py-2 hover:bg-base-200/50 transition-colors cursor-pointer list-none items-center",
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
                    Span("▶", cls="text-[8px] opacity-40 mr-2 group-open:rotate-90 transition-transform inline-block"),
                    Span("📁", cls="mr-2 opacity-50"),
                    B(category.name.upper()),
                    cls="col-span-5 flex items-center text-xs font-bold opacity-60 ml-[-0.5em]",
                ),
                Div(cat_overwrites_ui, cls="col-span-7"),
                cls="grid grid-cols-12 gap-2 px-4 py-2 hover:bg-base-200/50 transition-colors cursor-pointer list-none items-center bg-base-content/5",
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

    return Card(
        "Guild Channels",
        Div(_get_common_legend(for_roles=False), guild_section),
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

    # Calculate stats
    admin_roles_count = 0
    warnings = []

    for r in roles:
        if r.permissions & (1 << 3) and not r.is_managed:
            admin_roles_count += 1

        # Check @everyone role (ID usually matches guild_id, but the position is always 0)
        if r.position == 0:
            if r.permissions & (1 << 3):
                warnings.append("⚠️ @everyone has Administrator")
            if r.permissions & (1 << 5):
                warnings.append("⚠️ @everyone can Manage Guild")
            if r.permissions & (1 << 4):
                warnings.append("⚠️ @everyone can Manage Channels")
            if r.permissions & (1 << 28):
                warnings.append("⚠️ @everyone can Manage Roles")
            if r.permissions & (1 << 17):
                warnings.append("⚠️ @everyone can Mention Everyone")

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

    stats_grid = Div(
        Div(
            Div("Total Roles", cls="stat-title text-xs opacity-70"),
            Div(str(len(roles)), cls="stat-value text-2xl"),
            cls="stat bg-base-200/30 rounded-box p-3 shadow-inner",
        ),
        Div(
            Div("Total Channels", cls="stat-title text-xs opacity-70"),
            Div(str(len(channels)), cls="stat-value text-2xl"),
            cls="stat bg-base-200/30 rounded-box p-3 shadow-inner",
        ),
        Div(
            Div("Admin Roles", cls="stat-title text-xs text-error opacity-90"),
            Div(str(admin_roles_count), cls="stat-value text-2xl text-error"),
            cls="stat bg-base-200/30 rounded-box p-3 shadow-inner",
        ),
        Div(
            Div("Private Channels", cls="stat-title text-xs text-info opacity-90"),
            Div(str(private_channels_count), cls="stat-value text-2xl text-info"),
            cls="stat bg-base-200/30 rounded-box p-3 shadow-inner",
        ),
        cls="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4",
    )

    warnings_ui = ""
    if warnings:
        warnings_ui = Div(
            H4("Security Warnings", cls="font-bold text-error mb-2 text-sm"),
            Ul(*[Li(w) for w in warnings], cls="list-none text-xs text-error/90 space-y-1"),
            cls="p-3 bg-error/10 border left-border-error border-error/30 rounded-md mt-4",
        )
    else:
        warnings_ui = Div(
            "✅ No immediate security warnings detected for @everyone.", cls="text-success text-xs mt-4 opacity-80"
        )

    return Card("Security Overview", Div(stats_grid, warnings_ui), id=f"guild-admin-security-overview-{guild_id}")


def guild_admin_audit_permissions_widget(guild_id: int):
    """Displays a matrix correlating permissions to roles."""
    with Session(engine) as session:
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()

    if not roles:
        return Card(
            "Start Audit to view Permissions Matrix",
            Div("No roles found for this server.", cls="opacity-70 text-sm mt-2"),
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
                    color_css = ""
                    if role.color:
                        # Calculate perceived lightness to determine text color
                        hex_str = f"{role.color:06x}"
                        r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                        # Standard relative luminance calculation (simplified)
                        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                        text_color = "#000000" if luminance > 0.5 else "#ffffff"
                        color_css = f"background-color: #{hex_str}; color: {text_color}; border-color: #{hex_str};"

                    badge = Span(
                        role.name,
                        cls="inline-flex items-center px-2 py-0.5 rounded-md mr-1 mb-1 text-xs font-medium border border-base-content/10",
                        style=color_css,
                    )
                    roles_with_perm.append(badge)

            if not roles_with_perm:
                roles_ui = Span("None", cls="opacity-50 text-xs italic")
            else:
                roles_ui = Div(*roles_with_perm, cls="flex flex-wrap")

            highlight_class = "text-error font-bold" if perm_name == "Administrator" else "font-medium"

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

    return Card(
        "Permissions Matrix",
        Div(
            P(
                "Overview indicating which roles currently possess sensitive administrative or moderation permissions.",
                cls="text-xs opacity-70 mb-2",
            ),
            primary_table,
            secondary_table,
        ),
        id=f"guild-admin-audit-permissions-{guild_id}",
    )
