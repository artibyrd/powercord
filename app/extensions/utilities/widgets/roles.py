# mypy: ignore-errors
"""FastHTML widget for inspecting guild roles and permission badges."""

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.common.discord_constants import ALL_PERMISSIONS
from app.db.models import DiscordRole
from app.extensions.utilities.security_engine.constants import high_risk_perms, medium_risk_perms
from app.ui.components import Accordion

engine = init_connection_engine()


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
