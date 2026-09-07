# mypy: ignore-errors
"""Auxiliary FastHTML widgets for the utilities sidebar and help bubble."""

import json
from typing import Optional

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.db.models import DiscordChannel, DiscordRole
from app.extensions.utilities.security_engine.engine import SecurityRuleEngine
from app.ui.components import Card

engine = init_connection_engine()


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
    """Dashboard sidebar navigation and health status widget."""
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

    dismiss_script = Script(
        NotStr(f"""
(function() {{
    function initHelpBubble() {{
        const card = document.getElementById('help-bubble-card-{guild_id}');
        const container = document.getElementById('guild-admin-utilities-help-bubble-{guild_id}');
        if (!card || !container) return;
        document.addEventListener('click', function(e) {{
            if (!container.contains(e.target) && !card.classList.contains('hidden')) {{
                card.classList.add('hidden');
            }}
        }});
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape' && !card.classList.contains('hidden')) {{
                card.classList.add('hidden');
            }}
        }});
    }}
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', initHelpBubble);
    }} else {{
        initHelpBubble();
    }}
}})();
""")
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
                    "Connecting...",
                    id=f"bot-latency-display-{guild_id}",
                    hx_get=f"/dashboard/{guild_id}/ping-bot",
                    hx_trigger="load",
                    hx_swap="outerHTML",
                    cls="badge badge-warning badge-sm text-warning-content",
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
        cls="hidden absolute bottom-16 right-0 w-80 max-h-[80vh] overflow-y-auto bg-neutral/95 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl p-4 z-50 text-left",
    )

    toggle_btn = Button(
        help_icon_svg,
        onclick=f"document.getElementById('help-bubble-card-{guild_id}').classList.toggle('hidden')",
        cls="btn btn-circle btn-lg text-primary hover:text-secondary shadow-lg hover:scale-110 active:scale-95 transition-all duration-200",
        style="border-radius: 50% !important; background-color: hsl(var(--n) / 0.8) !important; backdrop-filter: blur(8px) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important;",
    )

    return Div(
        card_content, toggle_btn, dismiss_script, id=f"guild-admin-utilities-help-bubble-{guild_id}", cls="relative"
    )


def guild_admin_utilities_help_bubble(guild_id: int, session: Optional[Session] = None) -> FT:
    """Floating help bubble widget providing slash command cheatsheet and connection ping."""
    return _render_utilities_help_bubble(guild_id, session)


guild_admin_utilities_help_bubble.position_config = "bottom-right"
