# mypy: ignore-errors
"""HTMX modal dialogs for security rules information and alert overrides."""

from fasthtml.common import *
from sqlmodel import Session

from app.common.alchemy import init_connection_engine
from app.extensions.utilities.security_engine.engine import SecurityRuleEngine

engine = init_connection_engine()


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


def get_override_confirm_modal_html(guild_id: int, alert_hash: str) -> FT:
    """Generates a modal dialog allowing guild administrators to confirm overriding an alert."""
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
