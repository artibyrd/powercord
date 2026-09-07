# mypy: ignore-errors
import sys
from typing import Any

from fasthtml.common import *
from fasthtml.core import APIRouter

from app.common.extension_loader import GadgetInspector
from app.ui.components import Card
from app.ui.dashboard.grid import _get_ordered_widgets, _humanize_widget_name
from app.ui.dashboard.roles import _check_guild_admin
from app.ui.helpers import (
    SCOPE_ADMIN_DASHBOARD,
    SCOPE_PUBLIC,
    get_admin_guilds,
    get_widget_name,
    restore_default_widget_settings,
    update_widget_setting,
)
from app.ui.page import DashboardPage

layout_router = APIRouter()


POS_NAMES = {
    "left": "Left Sidebar",
    "right": "Right Sidebar",
    "bottom-right": "Bottom Right",
    "bottom-left": "Bottom Left",
    "top-right": "Top Right",
    "top-left": "Top Left",
}


def _dh(name: str, default: Any) -> Any:
    mod = sys.modules.get("app.ui.dashboard")
    if mod is not None and hasattr(mod, name):
        return getattr(mod, name)
    return default


def _render_layout_editor(widgets: list[dict], scope_id: int):
    """Render the layout editor table + live preview as an HTMX fragment."""
    inspector_cls = _dh("GadgetInspector", GadgetInspector)
    inspector = inspector_cls()
    all_widgets_by_ext = inspector.inspect_widgets()
    widget_defaults = {}
    get_name_fn = _dh("get_widget_name", get_widget_name)
    for _ext_name, widget_funcs in all_widgets_by_ext.items():
        for func in widget_funcs:
            wname = get_name_fn(func)
            if wname:
                widget_defaults[wname] = getattr(func, "default_pos", None) or getattr(func, "position_config", None)

    active_positions = {}
    for w in widgets:
        if w.get("enabled"):
            wname = w["widget"]
            default_pos = w.get("default_pos") or widget_defaults.get(wname) or w.get("position_config")
            pos_cfg = w.get("position_config")
            if default_pos in ("left", "right"):
                pos_cfg = "right" if pos_cfg == "right" else "left"
            elif default_pos in ("bottom-right", "bottom-left", "top-right", "top-left"):
                if pos_cfg not in ("bottom-right", "bottom-left", "top-right", "top-left"):
                    pos_cfg = "bottom-right"
            else:
                pos_cfg = None
            if pos_cfg:
                active_positions[pos_cfg] = active_positions.get(pos_cfg, 0) + 1

    collisions = [pos for pos, count in active_positions.items() if count > 1]
    warning_banner = None
    if collisions:
        collision_labels = [POS_NAMES.get(pos, pos) for pos in collisions]
        warning_banner = Div(
            Span(
                f"⚠️ Position Conflict: Multiple widgets are active in: {', '.join(collision_labels)}. They may overlap.",
                cls="font-semibold",
            ),
            cls="alert alert-warning mb-4",
        )

    humanize_fn = _dh("_humanize_widget_name", _humanize_widget_name)
    rows = []
    for idx, w in enumerate(widgets):
        label = f"{w['ext'].replace('_', ' ').title()}: {humanize_fn(w['ext'], w['widget'])}"
        wname = w["widget"]
        default_pos = w.get("default_pos") or widget_defaults.get(wname) or w.get("position_config")
        pos_cfg = w.get("position_config")

        # Classify each widget and normalize/default pos_cfg
        if default_pos in ("left", "right"):
            pos_cfg = "right" if pos_cfg == "right" else "left"
            widget_type = "Sidebar"
            config_td = Td(
                Form(
                    Select(
                        Option("Left Sidebar", value="left", selected=(pos_cfg == "left")),
                        Option("Right Sidebar", value="right", selected=(pos_cfg == "right")),
                        name="value",
                        cls="select select-sm select-bordered",
                    ),
                    Hidden(name="ext", value=w["ext"]),
                    Hidden(name="widget", value=w["widget"]),
                    Hidden(name="field", value="position_config"),
                    Hidden(name="scope_id", value=str(scope_id)),
                    hx_post="/admin/layout/update",
                    hx_trigger="change",
                    hx_target="#layout-editor",
                    hx_swap="innerHTML",
                )
            )
        elif default_pos in ("bottom-right", "bottom-left", "top-right", "top-left"):
            if pos_cfg not in ("bottom-right", "bottom-left", "top-right", "top-left"):
                pos_cfg = "bottom-right"
            widget_type = "Floating"
            config_td = Td(
                Form(
                    Select(
                        Option("Bottom Right", value="bottom-right", selected=(pos_cfg == "bottom-right")),
                        Option("Bottom Left", value="bottom-left", selected=(pos_cfg == "bottom-left")),
                        Option("Top Right", value="top-right", selected=(pos_cfg == "top-right")),
                        Option("Top Left", value="top-left", selected=(pos_cfg == "top-left")),
                        name="value",
                        cls="select select-sm select-bordered",
                    ),
                    Hidden(name="ext", value=w["ext"]),
                    Hidden(name="widget", value=w["widget"]),
                    Hidden(name="field", value="position_config"),
                    Hidden(name="scope_id", value=str(scope_id)),
                    hx_post="/admin/layout/update",
                    hx_trigger="change",
                    hx_target="#layout-editor",
                    hx_swap="innerHTML",
                )
            )
        else:
            widget_type = "Grid"
            config_td = Td(
                Form(
                    Select(
                        *[Option(f"{n} Columns", value=str(n), selected=(n == w["span"])) for n in range(1, 13)],
                        name="value",
                        cls="select select-sm select-bordered",
                    ),
                    Hidden(name="ext", value=w["ext"]),
                    Hidden(name="widget", value=w["widget"]),
                    Hidden(name="field", value="column_span"),
                    Hidden(name="scope_id", value=str(scope_id)),
                    hx_post="/admin/layout/update",
                    hx_trigger="change",
                    hx_target="#layout-editor",
                    hx_swap="innerHTML",
                )
            )

        type_td = Td(widget_type)
        is_fixed_or_floating = default_pos in ("left", "right", "bottom-right", "bottom-left", "top-right", "top-left")

        rows.append(
            Tr(
                # Widget name
                Td(label, cls="font-semibold"),
                # Enabled toggle
                Td(
                    Form(
                        Input(
                            type="checkbox",
                            name="enabled",
                            value="on",
                            checked=w["enabled"],
                            cls="checkbox checkbox-sm checkbox-primary",
                        ),
                        Hidden(name="ext", value=w["ext"]),
                        Hidden(name="widget", value=w["widget"]),
                        Hidden(name="field", value="is_enabled"),
                        Hidden(name="scope_id", value=str(scope_id)),
                        hx_post="/admin/layout/update",
                        hx_trigger="change",
                        hx_target="#layout-editor",
                        hx_swap="innerHTML",
                    )
                ),
                # Widget Type
                type_td,
                # Widget Config
                config_td,
                # Reorder buttons
                Td(
                    ""
                    if is_fixed_or_floating
                    else Div(
                        Form(
                            Hidden(name="ext", value=w["ext"]),
                            Hidden(name="widget", value=w["widget"]),
                            Hidden(name="direction", value="up"),
                            Hidden(name="scope_id", value=str(scope_id)),
                            Button(I(cls="fa-solid fa-arrow-up"), cls="btn btn-ghost btn-xs", disabled=(idx == 0)),
                            hx_post="/admin/layout/move",
                            hx_target="#layout-editor",
                            hx_swap="innerHTML",
                        ),
                        Form(
                            Hidden(name="ext", value=w["ext"]),
                            Hidden(name="widget", value=w["widget"]),
                            Hidden(name="direction", value="down"),
                            Hidden(name="scope_id", value=str(scope_id)),
                            Button(
                                I(cls="fa-solid fa-arrow-down"),
                                cls="btn btn-ghost btn-xs",
                                disabled=(idx == len(widgets) - 1),
                            ),
                            hx_post="/admin/layout/move",
                            hx_target="#layout-editor",
                            hx_swap="innerHTML",
                        ),
                        cls="flex gap-1",
                    )
                ),
            )
        )

    table_content = Div(
        Table(
            Thead(Tr(Th("Widget"), Th("Enabled"), Th("Widget Type"), Th("Widget Config"), Th("Order"))),
            Tbody(*rows),
            cls="table table-zebra w-full",
        ),
        cls="overflow-x-auto",
    )

    if scope_id > 1:
        restore_form = Form(
            Hidden(name="scope_id", value=str(scope_id)),
            Button(
                I(cls="fa-solid fa-rotate-left mr-1"),
                "Restore Default Layout",
                cls="btn btn-outline btn-warning btn-xs",
                hx_confirm="Are you sure you want to restore the default layout? All custom positioning and sizing changes will be lost.",
            ),
            hx_post="/admin/layout/restore",
            hx_target="#layout-editor",
            hx_swap="innerHTML",
        )
        card_title = Div(
            H3("Widget Configuration", cls="card-title"),
            restore_form,
            cls="flex justify-between items-center w-full",
        )
    else:
        card_title = "Widget Configuration"

    table_card = Card(
        card_title,
        table_content,
    )

    # Live preview: shows widgets in a 12-column CSS grid
    preview_items = []
    for w in widgets:
        wname = w["widget"]
        default_pos = w.get("default_pos") or widget_defaults.get(wname) or w.get("position_config")
        if default_pos in ("left", "right", "bottom-right", "bottom-left", "top-right", "top-left"):
            continue  # Exclude from main grid live preview
        opacity = "opacity-100" if w["enabled"] else "opacity-30"
        # Styling widget boxes as mini-cards
        preview_items.append(
            Div(
                Div(
                    H5(w["ext"].replace("_", " ").title(), cls="font-bold text-xs opacity-70"),
                    Div(humanize_fn(w["ext"], w["widget"]), cls="text-sm font-semibold truncate"),
                    cls="card-body p-3 text-center",
                ),
                cls=f"card bg-base-100 shadow-sm border border-base-content/20 {opacity}",
                style=f"grid-column: span {w['span']};",
            )
        )

    preview_section = Div(
        H3("Live Preview", cls="text-lg font-bold mb-4 ml-1 opacity-80"),
        Div(
            *preview_items,
            cls="grid grid-cols-12 gap-4",
        ),
        cls="mt-8",
    )

    children = []
    if warning_banner:
        children.append(warning_banner)
    children.extend([table_card, preview_section])
    return Div(*children)


@layout_router("/admin/layout")
def layout_editor(sess):
    """Page for editing the PUBLIC homepage widget layout."""
    auth = sess.get("auth", {})
    get_ordered = _dh("_get_ordered_widgets", _get_ordered_widgets)
    render_layout = _dh("_render_layout_editor", _render_layout_editor)
    widgets = get_ordered(SCOPE_PUBLIC)

    return DashboardPage(
        "Edit Public Layout",
        Div(
            H1("Edit Public Layout", cls="text-3xl font-extrabold mb-6"),
            P(
                "Configure which widgets appear on the public homepage, their width, and display order.",
                cls="mb-8 opacity-80",
            ),
            Div(
                render_layout(widgets, SCOPE_PUBLIC),
                id="layout-editor",
            ),
        ),
        auth=auth,
        guild_id=None,
        guild_name=None,
        fixed_widgets=None,
        floating_widgets=None,
    )


@layout_router("/admin/layout/admin")
def admin_layout_editor(sess):
    """Page for editing the ADMIN dashboard widget layout."""
    auth = sess.get("auth", {})
    get_ordered = _dh("_get_ordered_widgets", _get_ordered_widgets)
    render_layout = _dh("_render_layout_editor", _render_layout_editor)
    widgets = get_ordered(SCOPE_ADMIN_DASHBOARD)

    return DashboardPage(
        "Edit Admin Layout",
        Div(
            H1("Edit Admin Layout", cls="text-3xl font-extrabold mb-6"),
            P(
                "Configure which widgets appear on the Admin Dashboard, their width, and display order.",
                cls="mb-8 opacity-80",
            ),
            Div(
                render_layout(widgets, SCOPE_ADMIN_DASHBOARD),
                id="layout-editor",
            ),
        ),
        auth=auth,
        guild_id=None,
        guild_name=None,
        fixed_widgets=None,
        floating_widgets=None,
    )


@layout_router("/dashboard/{guild_id:int}/layout")
async def guild_layout_editor(guild_id: int, sess):
    """Page for editing a GUILD dashboard widget layout."""
    auth = sess.get("auth", {})
    user_access_token = auth.get("token_data", {}).get("access_token")
    if not user_access_token:
        return Titled("Error", P("Could not retrieve necessary tokens."))

    try:
        user_id = int(auth.get("id"))
        admin_guilds = await get_admin_guilds(user_access_token, user_id)
        guild = admin_guilds.get(str(guild_id), {"name": "Unknown Server"})
    except Exception as e:
        return Titled("Error", P(f"Failed to fetch guild information: {e}"))

    is_guild_admin = (int(guild.get("permissions", 0)) & (1 << 3)) != 0
    if not is_guild_admin:
        return Titled("Error", P("Forbidden: Guild Administrator permissions required."))

    get_ordered = _dh("_get_ordered_widgets", _get_ordered_widgets)
    render_layout = _dh("_render_layout_editor", _render_layout_editor)
    widgets = get_ordered(guild_id)

    return DashboardPage(
        f"Edit Layout: {guild['name']}",
        Div(
            H1(f"Edit Layout: {guild['name']}", cls="text-3xl font-extrabold mb-6"),
            P(
                "Configure which widgets appear on this Guild Dashboard, their width, and display order.",
                cls="mb-8 opacity-80",
            ),
            Div(
                render_layout(widgets, guild_id),
                id="layout-editor",
            ),
            A("Back to Dashboard", href=f"/dashboard/{guild_id}", role="button", cls="secondary mt-8 inline-block"),
        ),
        auth=auth,
        guild_id=guild_id,
        guild_name=guild["name"],
        guild_icon=guild.get("icon"),
        fixed_widgets=None,
        floating_widgets=None,
    )


@layout_router("/admin/layout/update", methods=["POST"])
async def layout_update(req):
    """Handles updating a single widget setting (enabled or column_span)."""
    form = await req.form()
    ext = form.get("ext")
    widget = form.get("widget")
    field = form.get("field")
    raw_scope = form.get("scope_id", "")
    scope_id = int(raw_scope) if raw_scope else SCOPE_PUBLIC

    check_admin_fn = _dh("_check_guild_admin", _check_guild_admin)
    if scope_id > 0:
        if not await check_admin_fn(scope_id, req):
            return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    if field == "is_enabled":
        value = form.get("enabled") == "on"
    elif field == "column_span":
        value = int(form.get("value", 4))
    elif field == "position_config":
        value = form.get("value")
    else:
        return P("Unknown field", cls="text-error")

    update_fn = _dh("update_widget_setting", update_widget_setting)
    update_fn(scope_id, ext, widget, field, value)

    get_ordered = _dh("_get_ordered_widgets", _get_ordered_widgets)
    render_layout = _dh("_render_layout_editor", _render_layout_editor)

    widgets = get_ordered(scope_id)
    if field == "is_enabled":
        for new_order, w in enumerate(widgets):
            update_fn(scope_id, w["ext"], w["widget"], "display_order", new_order)
        widgets = get_ordered(scope_id)
    return render_layout(widgets, scope_id)


@layout_router("/admin/layout/move", methods=["POST"])
async def layout_move(req):
    """Handles reordering a widget up or down."""
    form = await req.form()
    ext = form.get("ext")
    widget_name = form.get("widget")
    direction = form.get("direction")
    raw_scope = form.get("scope_id", "")
    scope_id = int(raw_scope) if raw_scope else SCOPE_PUBLIC

    check_admin_fn = _dh("_check_guild_admin", _check_guild_admin)
    if scope_id > 0:
        if not await check_admin_fn(scope_id, req):
            return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    get_ordered = _dh("_get_ordered_widgets", _get_ordered_widgets)
    render_layout = _dh("_render_layout_editor", _render_layout_editor)
    update_fn = _dh("update_widget_setting", update_widget_setting)

    widgets = get_ordered(scope_id)

    idx = next((i for i, w in enumerate(widgets) if w["ext"] == ext and w["widget"] == widget_name), None)
    if idx is None:
        return render_layout(widgets, scope_id)

    if direction == "up" and idx > 0:
        widgets[idx], widgets[idx - 1] = widgets[idx - 1], widgets[idx]
    elif direction == "down" and idx < len(widgets) - 1:
        widgets[idx], widgets[idx + 1] = widgets[idx + 1], widgets[idx]

    for new_order, w in enumerate(widgets):
        update_fn(scope_id, w["ext"], w["widget"], "display_order", new_order)

    widgets = get_ordered(scope_id)
    return render_layout(widgets, scope_id)


@layout_router("/admin/layout/restore", methods=["POST"])
async def layout_restore(req):
    """Handles restoring the default widget layout for a given scope/guild."""
    form = await req.form()
    raw_scope = form.get("scope_id", "")
    scope_id = int(raw_scope) if raw_scope else SCOPE_PUBLIC

    check_admin_fn = _dh("_check_guild_admin", _check_guild_admin)
    if scope_id > 0:
        if not await check_admin_fn(scope_id, req):
            return P("Forbidden: Guild Administrator permissions required.", cls="text-error")

    helpers_mod = sys.modules.get("app.ui.helpers")
    restore_fn = getattr(helpers_mod, "restore_default_widget_settings", restore_default_widget_settings)
    restore_fn(scope_id)

    get_ordered = _dh("_get_ordered_widgets", _get_ordered_widgets)
    render_layout = _dh("_render_layout_editor", _render_layout_editor)

    widgets = get_ordered(scope_id)
    return render_layout(widgets, scope_id)
