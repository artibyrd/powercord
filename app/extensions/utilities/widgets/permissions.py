# mypy: ignore-errors
"""FastHTML widget for displaying role-to-permission matrix."""

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.common.discord_constants import OTHER_PERMISSIONS, SENSITIVE_PERMISSIONS
from app.db.models import DiscordRole
from app.ui.components import Accordion

engine = init_connection_engine()


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
