# mypy: ignore-errors
"""FastHTML widget providing high-level security overview and breakdown."""

import json
import logging

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.db.models import DiscordChannel, DiscordRole
from app.extensions.utilities.security_engine.engine import SecurityRuleEngine
from app.ui.components import Card, HealthScoreArc, ProgressBarStat, SegmentedDigit

engine = init_connection_engine()


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
