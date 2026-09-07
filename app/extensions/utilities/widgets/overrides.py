# mypy: ignore-errors
"""FastHTML widget for displaying and managing security alert overrides."""

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.db.models import SecurityAlertOverride
from app.ui.components import Card

engine = init_connection_engine()


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
