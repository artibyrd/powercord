# mypy: ignore-errors
"""Alert list component rendering for the security auditor widget."""

from typing import Optional

from fasthtml.common import *

from app.extensions.utilities.security_engine.calculations import compute_alert_hash
from app.extensions.utilities.views.formatters import format_details, format_message


def _render_alerts_list(alerts: list[dict], guild_id: int, active_hashes: Optional[set[str]] = None) -> FT:
    """Renders structured alert rows with severity indicators, action buttons, and cascading details."""
    if not alerts:
        return Div("No security alerts found.", cls="text-sm opacity-70 p-4 text-center")

    if active_hashes is None:
        active_hashes = {a["alert_hash"] for a in alerts}

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
            alert_hash = compute_alert_hash(
                alert.get("rule", ""),
                alert.get("category", ""),
                alert.get("message", ""),
            )
        buttons.append(
            Button(
                "Override",
                hx_get=f"/dashboard/{guild_id}/alerts/override-confirm?alert_hash={alert_hash}",
                hx_target="#modal-container",
                hx_swap="innerHTML",
                cls="btn btn-xs btn-outline btn-warning ml-auto",
            )
        )

        # Parent/child rendering configurations
        parent_badge = ""
        if alert.get("child_count", 0) > 0:
            parent_badge = Span(
                f"→ {alert['child_count']} downstream",
                cls="badge badge-outline badge-accent badge-sm ml-2 tooltip tooltip-right cursor-help font-semibold",
                data_tip="Resolving this upstream alert could automatically resolve these downstream alerts",
            )

        child_indicator = ""
        is_child = False
        phash = alert.get("parent_hash")
        if phash and phash in active_hashes:
            parent_rule = alert.get("parent_rule", "Upstream Rule")
            parent_visible_in_tab = any(a["alert_hash"] == phash for a in alerts)

            if parent_visible_in_tab:
                # Parent is in this tab, style as indented child
                is_child = True
                child_indicator = Div(
                    I(cls="fa-solid fa-level-up-alt fa-rotate-90 text-[10px] opacity-50 mr-1.5"),
                    Span(
                        f"Cascaded from: {parent_rule}", cls="text-[10px] font-bold opacity-50 uppercase tracking-wider"
                    ),
                    cls="flex items-center mb-1.5",
                )
            else:
                # Parent is NOT in this tab, show indicator but do not indent
                child_indicator = Div(
                    I(cls="fa-solid fa-triangle-exclamation text-[10px] text-warning mr-1.5"),
                    Span(
                        f"Associated with upstream alert: {parent_rule}",
                        cls="text-[10px] font-bold text-warning/80 uppercase tracking-wider",
                    ),
                    cls="flex items-center mb-1.5",
                )

        container_cls = f"p-3 rounded-md border-l-4 border {border_cls} mb-3 last:mb-0"
        if phash and phash in active_hashes:
            container_cls += " border-dashed opacity-90"
            if is_child:
                container_cls += " ml-8"

        alert_elements.append(
            Div(
                child_indicator,
                Div(
                    Span(
                        alert.get("rule", "Security Alert"),
                        cls=f"badge {badge_cls} badge-sm px-2.5 py-1 mr-2 font-bold",
                    ),
                    Span(
                        alert.get("category", "").upper(),
                        cls="text-[10px] uppercase font-bold text-secondary tracking-wider",
                    ),
                    parent_badge,
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
                cls=container_cls,
            )
        )
    return Div(*alert_elements)
