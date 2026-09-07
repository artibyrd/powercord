# mypy: ignore-errors
"""FastHTML widget for displaying filterable security alerts."""

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.db.models import DiscordAuditorConfig
from app.extensions.utilities.security_engine.engine import SecurityRuleEngine
from app.extensions.utilities.views.alerts_list import _render_alerts_list
from app.ui.components import Card, TabGroup

engine = init_connection_engine()


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

    active_hashes = {a.get("alert_hash", "") for a in alerts}

    if category != "all":
        alerts = [a for a in alerts if a.get("category", "").lower() == category.lower()]

    warning_banner = ""
    if not admin_role_configured:
        warning_banner = Div(
            I(cls="fa-solid fa-triangle-exclamation text-warning mr-2 text-lg"),
            Span(
                A(
                    "Lowest Admin Role",
                    href=f"#guild-admin-auditor-settings-{guild_id}",
                    cls="link link-hover text-warning font-semibold",
                ),
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
        _render_alerts_list(alerts, guild_id, active_hashes=active_hashes),
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
