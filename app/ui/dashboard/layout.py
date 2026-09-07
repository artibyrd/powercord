# mypy: ignore-errors
from __future__ import annotations

from fasthtml.common import *
from fasthtml.core import APIRouter

from app.common.extension_loader import GadgetInspector
from app.ui.dashboard.grid import _get_ordered_widgets, _humanize_widget_name
from app.ui.dashboard.placement import (
    VALID_FIXED_POSITIONS,
    VALID_FLOATING_POSITIONS,
    normalize_position_config,
)
from app.ui.dashboard.roles import _check_guild_admin
from app.ui.helpers import (
    SCOPE_ADMIN_DASHBOARD,
    SCOPE_PUBLIC,
    get_admin_guilds,
    get_widget_name,
    is_dashboard_admin,
    restore_default_widget_settings,
    update_widget_setting,
)
from app.ui.page import DashboardPage

layout_router = APIRouter()


def _render_layout_editor(widgets: list[dict], scope_id: int):
    """Render the layout editor table + live preview as an HTMX fragment."""
    inspector = GadgetInspector()
    all_widgets_by_ext = inspector.inspect_widgets()
    widget_defaults = {}
    for _ext_name, widget_funcs in all_widgets_by_ext.items():
        for func in widget_funcs:
            wname = get_widget_name(func)
            if wname:
                widget_defaults[wname] = getattr(func, "default_pos", None) or getattr(func, "position_config", None)

    active_positions = {}
    for w in widgets:
        if w.get("enabled"):
            wname = w["widget"]
            default_pos = w.get("default_pos")
            if default_pos is None:
                default_pos = widget_defaults.get(wname)
            if default_pos in VALID_FIXED_POSITIONS or default_pos in VALID_FLOATING_POSITIONS:
                norm_pos = normalize_position_config(w.get("position_config"), default_pos)
                active_positions[norm_pos] = wname

    rows = []
    for idx, w in enumerate(widgets):
        wname = w["widget"]
        human_name = _humanize_widget_name(w["ext"], wname)
        enabled = w["enabled"]
        span = w["span"]
        default_pos = w.get("default_pos")
        if default_pos is None:
            default_pos = widget_defaults.get(wname)
        pos_cfg = w.get("position_config")

        is_fixed = default_pos in VALID_FIXED_POSITIONS
        is_floating = default_pos in VALID_FLOATING_POSITIONS

        if is_fixed:
            norm_pos = normalize_position_config(pos_cfg, default_pos)
            pos_label = f"Fixed Sidebar: {norm_pos.title()}"
        elif is_floating:
            norm_pos = normalize_position_config(pos_cfg, default_pos)
            pos_label = f"Floating: {norm_pos.replace('-', ' ').title()}"
        else:
            pos_label = "Grid"

        up_btn = (
            Button(
                I(cls="fa-solid fa-arrow-up"),
                cls="btn btn-ghost btn-xs text-base-content/70 hover:text-base-content",
                hx_post="/admin/layout/move",
                hx_vals=f'{{"widget": "{wname}", "ext": "{w["ext"]}", "direction": "up", "scope_id": {scope_id}}}',
                hx_target="#layout-editor-container",
                hx_swap="innerHTML",
            )
            if idx > 0
            else Button(
                I(cls="fa-solid fa-arrow-up"), cls="btn btn-ghost btn-xs opacity-20 cursor-not-allowed", disabled=True
            )
        )

        down_btn = (
            Button(
                I(cls="fa-solid fa-arrow-down"),
                cls="btn btn-ghost btn-xs text-base-content/70 hover:text-base-content",
                hx_post="/admin/layout/move",
                hx_vals=f'{{"widget": "{wname}", "ext": "{w["ext"]}", "direction": "down", "scope_id": {scope_id}}}',
                hx_target="#layout-editor-container",
                hx_swap="innerHTML",
            )
            if idx < len(widgets) - 1
            else Button(
                I(cls="fa-solid fa-arrow-down"), cls="btn btn-ghost btn-xs opacity-20 cursor-not-allowed", disabled=True
            )
        )

        toggle_input = Input(
            type="checkbox",
            name="enabled",
            checked=enabled,
            cls="toggle toggle-primary toggle-sm",
            hx_post="/admin/layout/update",
            hx_vals=f'{{"widget": "{wname}", "ext": "{w["ext"]}", "scope_id": {scope_id}}}',
            hx_target="#layout-editor-container",
            hx_swap="innerHTML",
        )

        span_options = [
            Option("3 Cols (1/4)", value="3", selected=(span == 3)),
            Option("4 Cols (1/3)", value="4", selected=(span == 4)),
            Option("6 Cols (1/2)", value="6", selected=(span == 6)),
            Option("8 Cols (2/3)", value="8", selected=(span == 8)),
            Option("12 Cols (Full)", value="12", selected=(span == 12)),
        ]
        span_select = Select(
            *span_options,
            name="span",
            cls="select select-bordered select-xs w-full max-w-[140px]",
            hx_post="/admin/layout/update",
            hx_vals=f'{{"widget": "{wname}", "ext": "{w["ext"]}", "scope_id": {scope_id}}}',
            hx_target="#layout-editor-container",
            hx_swap="innerHTML",
        )

        if is_fixed:
            norm_pos = normalize_position_config(pos_cfg, default_pos)
            pos_options = [
                Option("Left Sidebar", value="left", selected=(norm_pos == "left")),
                Option("Right Sidebar", value="right", selected=(norm_pos == "right")),
            ]
            config_control = Select(
                *pos_options,
                name="position_config",
                cls="select select-bordered select-xs w-full max-w-[140px]",
                hx_post="/admin/layout/update",
                hx_vals=f'{{"widget": "{wname}", "ext": "{w["ext"]}", "scope_id": {scope_id}}}',
                hx_target="#layout-editor-container",
                hx_swap="innerHTML",
            )
        elif is_floating:
            norm_pos = normalize_position_config(pos_cfg, default_pos)
            pos_options = [
                Option("Bottom Right", value="bottom-right", selected=(norm_pos == "bottom-right")),
                Option("Bottom Left", value="bottom-left", selected=(norm_pos == "bottom-left")),
                Option("Top Right", value="top-right", selected=(norm_pos == "top-right")),
                Option("Top Left", value="top-left", selected=(norm_pos == "top-left")),
            ]
            config_control = Select(
                *pos_options,
                name="position_config",
                cls="select select-bordered select-xs w-full max-w-[140px]",
                hx_post="/admin/layout/update",
                hx_vals=f'{{"widget": "{wname}", "ext": "{w["ext"]}", "scope_id": {scope_id}}}',
                hx_target="#layout-editor-container",
                hx_swap="innerHTML",
            )
        else:
            config_control = span_select

        warning_badge = ""
        if enabled and (is_fixed or is_floating):
            norm_pos = normalize_position_config(pos_cfg, default_pos)
            if active_positions.get(norm_pos) != wname:
                warning_badge = Div(
                    I(cls="fa-solid fa-triangle-exclamation mr-1"),
                    f"Position '{norm_pos}' collides with '{active_positions.get(norm_pos)}'",
                    cls="text-error text-xs mt-1",
                )

        row_cls = "hover:bg-base-200/50" if enabled else "opacity-50 hover:bg-base-200/30"

        rows.append(
            Tr(
                Td(Div(up_btn, down_btn, cls="flex gap-1 items-center")),
                Td(
                    Div(
                        Span(human_name, cls="font-semibold text-base-content"),
                        Span(f" ({w['ext']})", cls="text-xs text-base-content/50"),
                        warning_badge,
                    )
                ),
                Td(Span(pos_label, cls="badge badge-sm badge-ghost")),
                Td(toggle_input),
                Td(config_control),
                cls=row_cls,
            )
        )

    table = Table(
        Thead(
            Tr(
                Th("Order", cls="w-20"),
                Th("Widget Name"),
                Th("Position Type", cls="w-36"),
                Th("Enabled", cls="w-24"),
                Th("Width / Position", cls="w-48"),
            )
        ),
        Tbody(*rows),
        cls="table w-full",
    )

    preview_items = []
    for w in widgets:
        if w["enabled"]:
            wname = w["widget"]
            human_name = _humanize_widget_name(w["ext"], wname)
            default_pos = w.get("default_pos")
            if default_pos is None:
                default_pos = widget_defaults.get(wname)
            is_fixed = default_pos in VALID_FIXED_POSITIONS
            is_floating = default_pos in VALID_FLOATING_POSITIONS

            if is_fixed:
                norm_pos = normalize_position_config(w.get("position_config"), default_pos)
                preview_items.append(
                    Div(
                        Span(f"📌 {human_name}", cls="font-medium text-xs truncate"),
                        Span(f"Fixed ({norm_pos.title()})", cls="badge badge-xs badge-outline opacity-60 ml-auto"),
                        cls="bg-base-300/80 border border-primary/40 rounded p-2 flex items-center gap-2",
                        style="grid-column: span 12;",
                    )
                )
            elif is_floating:
                norm_pos = normalize_position_config(w.get("position_config"), default_pos)
                preview_items.append(
                    Div(
                        Span(f"🎈 {human_name}", cls="font-medium text-xs truncate"),
                        Span(f"Floating ({norm_pos})", cls="badge badge-xs badge-outline opacity-60 ml-auto"),
                        cls="bg-base-300/80 border border-secondary/40 rounded p-2 flex items-center gap-2",
                        style="grid-column: span 12;",
                    )
                )
            else:
                span = w["span"]
                preview_items.append(
                    Div(
                        Span(human_name, cls="font-medium text-xs truncate"),
                        Span(f"{span}/12", cls="badge badge-xs badge-ghost opacity-60 ml-auto"),
                        cls="bg-base-300/60 border border-base-content/20 rounded p-2 flex items-center gap-2",
                        style=f"grid-column: span {span};",
                    )
                )

    preview_grid = (
        Div(
            Div(*preview_items, cls="grid grid-cols-12 gap-2 p-4 bg-base-100 rounded-lg border border-base-content/10"),
            cls="mt-6",
        )
        if preview_items
        else P("No widgets currently enabled in this layout.", cls="italic opacity-60 mt-4 text-center")
    )

    return Div(
        table,
        Div(
            H3("Live Layout Preview", cls="text-sm font-semibold opacity-70 mb-2"),
            preview_grid,
            cls="mt-6 border-t border-base-content/10 pt-4",
        ),
        id="layout-editor-container",
    )


@layout_router("/admin/layout")
def layout_editor(sess):
    """Layout editor page for Public Page (scope_id=0)."""
    widgets = _get_ordered_widgets(SCOPE_PUBLIC)
    editor = _render_layout_editor(widgets, SCOPE_PUBLIC)

    restore_btn = Button(
        I(cls="fa-solid fa-rotate-left mr-2"),
        "Restore Default Layout",
        cls="btn btn-outline btn-warning btn-sm",
        hx_post="/admin/layout/restore",
        hx_vals=f'{{"scope_id": {SCOPE_PUBLIC}}}',
        hx_target="#layout-editor-container",
        hx_swap="innerHTML",
        hx_confirm="Reset public widget layout to default positions and column spans?",
    )

    content = Div(
        Div(
            H1("Public Page Layout Editor", cls="text-2xl font-bold"),
            restore_btn,
            cls="flex justify-between items-center mb-6",
        ),
        Div(editor, cls="card bg-base-100 shadow-sm border border-base-content/20 p-4"),
    )

    return DashboardPage("Public Layout Editor", content, auth=sess.get("auth"))


@layout_router("/admin/layout/admin")
def admin_layout_editor(sess):
    """Layout editor page for Admin Dashboard (scope_id=1)."""
    auth = sess.get("auth", {})
    user_id = auth.get("id")
    is_admin = False
    if user_id:
        try:
            is_admin = is_dashboard_admin(int(user_id))
        except (ValueError, TypeError):
            pass

    if not is_admin:
        return DashboardPage("Access Denied", P("Forbidden", cls="text-error"), auth=auth)

    widgets = _get_ordered_widgets(SCOPE_ADMIN_DASHBOARD)
    editor = _render_layout_editor(widgets, SCOPE_ADMIN_DASHBOARD)

    restore_btn = Button(
        I(cls="fa-solid fa-rotate-left mr-2"),
        "Restore Default Layout",
        cls="btn btn-outline btn-warning btn-sm",
        hx_post="/admin/layout/restore",
        hx_vals=f'{{"scope_id": {SCOPE_ADMIN_DASHBOARD}}}',
        hx_target="#layout-editor-container",
        hx_swap="innerHTML",
        hx_confirm="Reset admin widget layout to defaults?",
    )

    content = Div(
        Div(
            H1("Admin Dashboard Layout Editor", cls="text-2xl font-bold"),
            restore_btn,
            cls="flex justify-between items-center mb-6",
        ),
        Div(editor, cls="card bg-base-100 shadow-sm border border-base-content/20 p-4"),
    )

    return DashboardPage("Admin Layout Editor", content, auth=auth)


@layout_router("/dashboard/{guild_id:int}/layout")
async def guild_layout_editor(guild_id: int, sess, req):
    """Layout editor page for Server Dashboard."""
    if not await _check_guild_admin(guild_id, req):
        return DashboardPage(
            "Access Denied",
            P("Forbidden: Guild Administrator permissions required.", cls="text-error"),
            auth=sess.get("auth"),
        )

    auth = sess.get("auth", {})
    guild_name = "Server"
    user_access_token = auth.get("token_data", {}).get("access_token")
    if user_access_token:
        try:
            admin_guilds = await get_admin_guilds(user_access_token, int(auth.get("id")))
            guild_name = admin_guilds.get(str(guild_id), {}).get("name", "Server")
        except Exception:  # noqa: S110
            pass

    widgets = _get_ordered_widgets(guild_id)
    editor = _render_layout_editor(widgets, guild_id)

    restore_btn = Button(
        I(cls="fa-solid fa-rotate-left mr-2"),
        "Restore Default Layout",
        cls="btn btn-outline btn-warning btn-sm",
        hx_post="/admin/layout/restore",
        hx_vals=f'{{"scope_id": {guild_id}}}',
        hx_target="#layout-editor-container",
        hx_swap="innerHTML",
        hx_confirm=f"Reset widget layout for '{guild_name}' to defaults?",
    )

    back_link = A(
        I(cls="fa-solid fa-arrow-left mr-2"),
        f"Back to {guild_name}",
        href=f"/dashboard/{guild_id}",
        cls="btn btn-ghost btn-sm mr-2",
    )

    content = Div(
        Div(
            Div(back_link, H1(f"Layout Editor: {guild_name}", cls="text-2xl font-bold"), cls="flex items-center"),
            restore_btn,
            cls="flex justify-between items-center mb-6",
        ),
        Div(editor, cls="card bg-base-100 shadow-sm border border-base-content/20 p-4"),
    )

    return DashboardPage(f"Layout Editor: {guild_name}", content, auth=auth, guild_id=guild_id, guild_name=guild_name)


@layout_router("/admin/layout/update", methods=["POST"])
async def layout_update(req):
    """Handles enabling/disabling widgets or changing column spans/position configs."""
    form = await req.form()
    widget_name = form.get("widget")
    ext_name = form.get("ext")
    raw_scope = form.get("scope_id", "")
    scope_id = int(raw_scope) if raw_scope else SCOPE_PUBLIC

    if scope_id > 0:
        if not await _check_guild_admin(scope_id, req):
            return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    if "enabled" in form:
        is_enabled = form.get("enabled") == "on"
        update_widget_setting(scope_id, ext_name, widget_name, "is_enabled", is_enabled)

    if "span" in form:
        try:
            span = int(form.get("span"))
            update_widget_setting(scope_id, ext_name, widget_name, "column_span", span)
        except ValueError:
            pass

    if "position_config" in form:
        pos_cfg = form.get("position_config")
        update_widget_setting(scope_id, ext_name, widget_name, "position_config", pos_cfg)

    widgets = _get_ordered_widgets(scope_id)
    return _render_layout_editor(widgets, scope_id)


@layout_router("/admin/layout/move", methods=["POST"])
async def layout_move(req):
    """Handles reordering widgets (moving up or down)."""
    form = await req.form()
    widget_name = form.get("widget")
    direction = form.get("direction")
    raw_scope = form.get("scope_id", "")
    scope_id = int(raw_scope) if raw_scope else SCOPE_PUBLIC

    if scope_id > 0:
        if not await _check_guild_admin(scope_id, req):
            return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    widgets = _get_ordered_widgets(scope_id)
    idx = next((i for i, w in enumerate(widgets) if w["widget"] == widget_name), -1)
    if idx == -1:
        return _render_layout_editor(widgets, scope_id)

    if direction == "up" and idx > 0:
        widgets[idx], widgets[idx - 1] = widgets[idx - 1], widgets[idx]
    elif direction == "down" and idx < len(widgets) - 1:
        widgets[idx], widgets[idx + 1] = widgets[idx + 1], widgets[idx]

    for new_order, w in enumerate(widgets):
        update_widget_setting(scope_id, w["ext"], w["widget"], "display_order", new_order)

    widgets = _get_ordered_widgets(scope_id)
    return _render_layout_editor(widgets, scope_id)


@layout_router("/admin/layout/restore", methods=["POST"])
async def layout_restore(req):
    """Handles restoring the default widget layout for a given scope/guild."""
    form = await req.form()
    raw_scope = form.get("scope_id", "")
    scope_id = int(raw_scope) if raw_scope else SCOPE_PUBLIC

    if scope_id > 0:
        if not await _check_guild_admin(scope_id, req):
            return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    restore_default_widget_settings(scope_id)

    widgets = _get_ordered_widgets(scope_id)
    return _render_layout_editor(widgets, scope_id)
