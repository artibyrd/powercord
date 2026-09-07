# mypy: ignore-errors
from __future__ import annotations

import json
import sys

from fasthtml.common import *
from sqlmodel import Session, select

import app.ui.helpers as helpers
from app.common.alchemy import init_connection_engine
from app.db.models import ApiKey


def _init_engine():
    mod_alchemy = sys.modules.get("app.common.alchemy")
    if mod_alchemy and hasattr(mod_alchemy, "init_connection_engine"):
        return mod_alchemy.init_connection_engine()
    mod_helpers = sys.modules.get("app.ui.helpers")
    if mod_helpers and hasattr(mod_helpers, "init_connection_engine"):
        return mod_helpers.init_connection_engine()
    return init_connection_engine()


async def _render_admin_list(sess: dict) -> FT:
    auth = sess.get("auth", {})
    admins = helpers.get_dashboard_admins()

    admin_rows = []
    for admin in admins:
        username = await helpers.get_discord_username(admin.user_id)
        admin_rows.append(
            Tr(
                Td(str(admin.user_id)),
                Td(username, cls="font-semibold text-primary"),
                Td(admin.comment or ""),
                Td(
                    Form(
                        Hidden(name="user_id", value=str(admin.user_id)),
                        Button("Remove", cls="btn btn-error btn-xs"),
                        hx_post="/admin/manage/remove",
                        hx_target="#admin-list",
                        hx_swap="outerHTML",
                        method="post",
                        style="display:inline;",
                    )
                    if admin.user_id != int(auth.get("id"))
                    else Span("You", cls="badge badge-ghost")
                ),
            )
        )

    return Div(
        Table(
            Thead(Tr(Th("User ID"), Th("Username"), Th("Comment"), Th("Actions"))),
            Tbody(*admin_rows),
            cls="table w-full",
            id="admin-list-body",
        ),
        id="admin-list",
    )


async def _render_admin_api_keys(sess: dict) -> FT:
    engine = _init_engine()
    with Session(engine) as session:
        stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
        keys = session.exec(stmt).all()

    key_rows = []
    for k in keys:
        try:
            scopes_list = json.loads(k.scopes)
        except Exception:
            scopes_list = []
        scopes_str = ", ".join(scopes_list)

        status_badge = (
            Span("Active", cls="badge badge-success badge-sm")
            if k.is_active
            else Span("Inactive", cls="badge badge-ghost badge-sm")
        )

        action_btn = Form(
            Hidden(name="key_id", value=str(k.id)),
            Hidden(name="action", value="revoke" if k.is_active else "reactivate"),
            Button(
                "Revoke" if k.is_active else "Reactivate",
                cls=f"btn {'btn-warning' if k.is_active else 'btn-success'} btn-xs",
            ),
            hx_post="/admin/api-key/toggle",
            hx_target="#admin-api-keys-list",
            hx_swap="outerHTML",
            style="display:inline-block;",
        )

        key_rows.append(
            Tr(
                Td(str(k.id)),
                Td(k.name, cls="font-mono text-xs opacity-70"),
                Td(status_badge),
                Td(k.key_type, cls="text-xs"),
                Td(scopes_str, cls="font-mono text-xs max-w-xs truncate"),
                Td(k.created_at.strftime("%Y-%m-%d %H:%M:%S") if k.created_at else "N/A"),
                Td(action_btn),
            )
        )

    table = (
        Table(
            Thead(
                Tr(
                    Th("ID"),
                    Th("Name"),
                    Th("Status"),
                    Th("Type"),
                    Th("Scopes"),
                    Th("Created At"),
                    Th("Actions"),
                )
            ),
            Tbody(*key_rows),
            cls="table w-full",
        )
        if key_rows
        else P("No API keys found in database.", cls="italic opacity-70")
    )

    return Div(
        H2("Manage API Keys", cls="text-2xl font-bold mb-4"),
        Div(
            table,
            cls="card bg-base-100 shadow-sm border border-base-content/20 p-4 max-h-96 overflow-y-auto",
        ),
        id="admin-api-keys-list",
        cls="mb-8",
    )
