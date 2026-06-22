# ruff: noqa: E402
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fasthtml.common import Div, Response

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.ui.dashboard import lockdown_route, toggle_nav_route
from app.ui.page import DashboardPage, TopAppBar

pytestmark = pytest.mark.unit


def test_dashboard_page_rendering():
    """Verify that DashboardPage renders sidebar and navbar correctly with defaults."""
    title, div = DashboardPage("My Test title", Div("Hello World"))
    assert "My Test title" in str(title)

    html = str(div)
    # Check that TopAppBar is rendered
    assert "Powercord" in html
    assert "Hello World" in html
    assert "Dashboard Home" not in html


def test_top_app_bar():
    """Verify TopAppBar outputs correct branding when guild_id is provided."""
    top_bar = TopAppBar(auth=None, guild_id=98765)
    html = str(top_bar)
    assert "Powercord" in html
    assert "Server: 98765" in html
    assert "Lockdown" not in html


def test_top_app_bar_with_guild_name():
    """Verify TopAppBar displays the custom guild name when provided."""
    top_bar = TopAppBar(auth=None, guild_id=98765, guild_name="My Cool Server")
    html = str(top_bar)
    assert "Powercord" in html
    assert "My Cool Server" in html
    assert "Server: 98765" not in html
    assert "Lockdown" not in html


def test_top_app_bar_with_guild_icon():
    """Verify TopAppBar displays the custom guild icon image when provided."""
    top_bar = TopAppBar(auth=None, guild_id=98765, guild_name="My Cool Server", guild_icon="icon_hash_123")
    html = str(top_bar)
    assert "cdn.discordapp.com/icons/98765/icon_hash_123.png" in html
    assert "fa-server" not in html


def test_top_app_bar_with_guild_icon_fallback():
    """Verify TopAppBar falls back to the generic server icon when no icon hash is provided."""
    top_bar = TopAppBar(auth=None, guild_id=98765, guild_name="My Cool Server", guild_icon=None)
    html = str(top_bar)
    assert "cdn.discordapp.com/icons/" not in html
    assert "fa-server" in html


def test_dashboard_page_accepts_widget_parameters():
    """Verify that DashboardPage signature accepts new widget parameters successfully."""
    title, div = DashboardPage(
        "Test Title",
        Div("Content"),
        guild_name="Some Guild Name",
        fixed_widgets=["mock_widget"],
        floating_widgets=["mock_widget"],
    )
    assert "Test Title" in str(title)
    assert "Content" in str(div)


def test_dashboard_page_guild_name_edge_cases():
    """Verify that passing edge-case values for guild_name handles it correctly."""
    # 1. Empty string
    top_bar_empty = TopAppBar(auth=None, guild_id=123, guild_name="")
    html_empty = str(top_bar_empty)
    assert "Server: 123" not in html_empty
    assert '<span class="font-semibold text-sm"></span>' in html_empty

    # 2. None
    top_bar_none = TopAppBar(auth=None, guild_id=123, guild_name=None)
    html_none = str(top_bar_none)
    assert "Server: 123" in html_none

    # 3. Special characters (checking standard HTML escaping)
    special_name = "<b>Cool</b> & <script>alert(1)</script>"
    top_bar_special = TopAppBar(auth=None, guild_id=123, guild_name=special_name)
    html_special = str(top_bar_special)
    assert "&lt;b&gt;Cool&lt;/b&gt; &amp; &lt;script&gt;alert(1)&lt;/script&gt;" in html_special

    # 4. Long string
    long_name = "A" * 1000
    top_bar_long = TopAppBar(auth=None, guild_id=123, guild_name=long_name)
    html_long = str(top_bar_long)
    assert long_name in html_long


def test_dashboard_page_widget_parameters_details():
    """Verify that fixed_widgets and floating_widgets do not crash the rendering when provided, empty, or omitted."""
    # Omitted (already verified in test_dashboard_page_rendering)
    # Empty lists
    title_empty, div_empty = DashboardPage("Title", Div("Content"), fixed_widgets=[], floating_widgets=[])
    assert "Content" in str(div_empty)

    # Populated lists (various types of data)
    title_filled, div_filled = DashboardPage(
        "Title", Div("Content"), fixed_widgets=["widget1", {"name": "widget2"}], floating_widgets=[None, 123]
    )
    assert "Content" in str(div_filled)


@pytest.mark.asyncio
async def test_lockdown_route():
    """Verify the lockdown endpoint returns a DaisyUI alert."""
    resp = await lockdown_route(guild_id=12345)
    html = str(resp)
    assert "Emergency Lockdown Initiated!" in html
    assert "alert-error" in html


@pytest.mark.asyncio
@patch("app.common.alchemy.init_connection_engine")
async def test_toggle_nav_route(mock_init_engine):
    """Verify toggle_nav_route updates the UserSetting in the database."""
    # Setup mocks
    mock_session_obj = MagicMock()
    mock_session_obj.get.return_value = None  # user_setting doesn't exist

    with patch("sqlmodel.Session") as mock_session_cls:
        mock_session_cls.return_value.__enter__.return_value = mock_session_obj

        sess = {"auth": {"id": "12345"}}

        req = MagicMock()
        req.query_params = {"show_topbar": "false"}
        req.form = AsyncMock(return_value={})

        resp = await toggle_nav_route(guild_id=12345, req=req, sess=sess)

        # Verify it returns HX-Refresh header
        assert isinstance(resp, Response)
        assert resp.headers.get("HX-Refresh") == "true"

        # Verify db interaction
        mock_session_obj.add.assert_called_once()
        mock_session_obj.commit.assert_called_once()

        # Verify it set show_topbar to False
        added_obj = mock_session_obj.add.call_args[0][0]
        assert added_obj.user_id == 12345
        assert added_obj.show_topbar is False


def test_dashboard_page_fixed_and_floating_widgets_layout():
    """Verify that DashboardPage renders fixed and floating widgets correctly with proper styles/margins."""
    # Define fixed and floating widgets using both dictionary format and direct components
    # 1. Left fixed widget (as component directly)
    left_widget = Div("Left Widget Component", id="left-w")
    left_widget.position_config = "left"

    # 2. Right fixed widget (as dictionary)
    right_widget = {
        "component": Div("Right Widget Component", id="right-w"),
        "position_config": "right",
    }

    # 3. Floating widgets (using various positions, dict and direct components)
    float_br = {
        "component": Div("Float Bottom Right", id="float-br"),
        "position_config": "bottom-right",
    }
    float_bl = Div("Float Bottom Left", id="float-bl")
    float_bl.position_config = "bottom-left"

    float_tr = {
        "component": Div("Float Top Right", id="float-tr"),
        "position_config": "top-right",
    }
    float_tl = Div("Float Top Left", id="float-tl")
    float_tl.position_config = "top-left"

    # Call DashboardPage
    _, div = DashboardPage(
        "Layout Test",
        Div("Main Content Area", id="main-content"),
        fixed_widgets=[left_widget, right_widget],
        floating_widgets=[float_br, float_bl, float_tr, float_tl],
    )

    html = str(div)

    # 1. Verify margin-left: 312px; and margin-right: 312px; in the content panel.
    assert "margin-left: 312px;" in html
    assert "margin-right: 312px;" in html

    # 2. Verify left and right panels with exact styles and existence of fixed widgets.
    assert (
        'style="position: fixed; left: 16px; top: 80px; bottom: 16px; width: 280px; overflow-y: auto; z-index: 40;"'
        in html
    )
    assert (
        'style="position: fixed; right: 16px; top: 80px; bottom: 16px; width: 280px; overflow-y: auto; z-index: 40;"'
        in html
    )
    assert "Left Widget Component" in html
    assert "Right Widget Component" in html

    # 3. Verify floating widget containers style properties.
    assert 'style="position: fixed; z-index: 50; bottom: 20px; right: 20px;"' in html
    assert 'style="position: fixed; z-index: 50; bottom: 20px; left: 20px;"' in html
    assert 'style="position: fixed; z-index: 50; top: 100px; right: 20px;"' in html
    assert 'style="position: fixed; z-index: 50; top: 100px; left: 20px;"' in html
    assert "Float Bottom Right" in html
    assert "Float Bottom Left" in html
    assert "Float Top Right" in html
    assert "Float Top Left" in html


def test_dashboard_page_multiple_widgets_same_side():
    """Verify that multiple fixed widgets on the same/opposite sides don't double margin shift or crash."""
    # 1. Multiple widgets on left side
    _, div_left = DashboardPage(
        "Title",
        Div("Content"),
        fixed_widgets=[Div("Left Widget 1", position_config="left"), Div("Left Widget 2", position_config="left")],
    )
    html_left = str(div_left)
    assert html_left.count("margin-left: 312px;") == 1
    assert "Left Widget 1" in html_left
    assert "Left Widget 2" in html_left

    # 2. Multiple widgets on right side
    _, div_right = DashboardPage(
        "Title",
        Div("Content"),
        fixed_widgets=[Div("Right Widget 1", position_config="right"), Div("Right Widget 2", position_config="right")],
    )
    html_right = str(div_right)
    assert html_right.count("margin-right: 312px;") == 1
    assert "Right Widget 1" in html_right
    assert "Right Widget 2" in html_right

    # 3. Widgets on opposite sides
    _, div_both = DashboardPage(
        "Title",
        Div("Content"),
        fixed_widgets=[Div("Left Widget", position_config="left"), Div("Right Widget", position_config="right")],
    )
    html_both = str(div_both)
    assert html_both.count("margin-left: 312px;") == 1
    assert html_both.count("margin-right: 312px;") == 1


def test_dashboard_page_non_iterable_containers_crash():
    """Verify that passing non-iterable containers (like integer, boolean) as widgets parameters raises TypeError."""
    with pytest.raises(TypeError):
        DashboardPage("Title", Div("Content"), fixed_widgets=123)

    with pytest.raises(TypeError):
        DashboardPage("Title", Div("Content"), floating_widgets=True)


def test_dashboard_page_single_component_direct_loss():
    """Verify that passing a single Component directly results in its outer class/styles being discarded (treated as iterable of children)."""
    widget = Div("Widget Inner Text", cls="custom-widget-class")
    widget.position_config = "left"

    _, div = DashboardPage("Title", Div("Content"), fixed_widgets=widget)
    html = str(div)
    # The outer Div class should be present, but due to direct iteration, it gets stripped
    # and only 'Widget Inner Text' is rendered directly inside the sidebar.
    assert "custom-widget-class" not in html
    assert "Widget Inner Text" in html


def test_dashboard_page_string_directly_char_by_char():
    """Verify that passing a string directly results in character-by-character rendering inside the sidebar."""
    # If "right" is passed as a string directly, if it were treated as a single widget,
    # it would not trigger left sidebar margin since it has no position_config (or would go to right sidebar if named 'right').
    # But because it iterates char-by-char, it parses 'r', 'i', 'g', 'h', 't', none of which are 'right',
    # and appends them all to the left sidebar, which triggers margin-left: 280px.
    _, div = DashboardPage("Title", Div("Content"), fixed_widgets="right")
    html = str(div)
    assert "margin-left: 312px;" in html
    assert "margin-right: 312px;" not in html


@patch("app.ui.dashboard.get_widget_settings")
@patch("app.ui.dashboard.is_gadget_enabled")
@patch("app.ui.dashboard.GadgetInspector")
def test_get_ordered_widgets_includes_position_config(
    mock_inspector_cls, mock_is_gadget_enabled, mock_get_widget_settings
):
    # Setup mock widget function with position_config attribute
    def mock_widget_func():
        pass

    mock_widget_func.position_config = "left"
    mock_widget_func.__name__ = "guild_admin_test_widget"

    mock_inspector = MagicMock()
    mock_inspector.inspect_widgets.return_value = {"test_ext": [mock_widget_func]}
    mock_inspector_cls.return_value = mock_inspector

    mock_is_gadget_enabled.return_value = True
    # Test 1: position_config from settings overrides function default
    mock_get_widget_settings.return_value = {
        "guild_admin_test_widget": {
            "is_enabled": True,
            "column_span": 6,
            "display_order": 2,
            "position_config": "right",
        }
    }

    from app.ui.dashboard import _get_ordered_widgets

    widgets = _get_ordered_widgets(2)

    assert len(widgets) == 1
    assert widgets[0]["position_config"] == "right"

    # Test 2: fallback to function default when settings position_config is None
    mock_get_widget_settings.return_value = {
        "guild_admin_test_widget": {"is_enabled": True, "column_span": 6, "display_order": 2}
    }
    widgets = _get_ordered_widgets(2)
    assert len(widgets) == 1
    assert widgets[0]["position_config"] == "left"


def test_render_layout_editor_rendering():
    widgets = [
        {
            "ext": "test_ext",
            "widget": "guild_admin_widget_1",
            "enabled": True,
            "span": 4,
            "order": 1,
            "position_config": "left",
        },
        {
            "ext": "test_ext",
            "widget": "guild_admin_widget_2",
            "enabled": True,
            "span": 4,
            "order": 2,
            "position_config": "bottom-right",
        },
        {
            "ext": "test_ext",
            "widget": "guild_admin_widget_3",
            "enabled": True,
            "span": 4,
            "order": 3,
            "position_config": None,
        },
    ]

    from app.ui.dashboard import _render_layout_editor

    rendered = _render_layout_editor(widgets, 2)
    html = str(rendered)

    # 1. Verify "Widget Config" and "Widget Type" column headers are present
    assert "Widget Config" in html
    assert "Widget Type" in html

    # 2. Verify select dropdown for fixed widgets (options: Left/Right Sidebar)
    assert 'value="left"' in html
    assert 'value="right"' in html
    assert "Left Sidebar" in html
    assert "Right Sidebar" in html

    # 3. Verify select dropdown for floating widgets (options: Bottom Right, Bottom Left, etc.)
    assert 'value="bottom-right"' in html
    assert 'value="bottom-left"' in html
    assert "Bottom Right" in html
    assert "Bottom Left" in html

    # 4. Verify placeholder for other (grid) widgets
    assert "Grid" in html


@pytest.mark.asyncio
@patch("app.ui.dashboard.update_widget_setting")
@patch("app.ui.dashboard._get_ordered_widgets")
@patch("app.ui.dashboard._render_layout_editor")
async def test_layout_update_position_config(mock_render, mock_get_ordered, mock_update_setting):
    from app.ui.dashboard import layout_update

    mock_req = MagicMock()
    mock_req.form = AsyncMock(
        return_value={
            "ext": "test_ext",
            "widget": "guild_admin_widget",
            "field": "position_config",
            "value": "right",
            "scope_id": "2",
        }
    )

    mock_get_ordered.return_value = []
    mock_render.return_value = Div("Mocked Layout Editor")

    await layout_update(mock_req)

    mock_update_setting.assert_called_once_with(2, "test_ext", "guild_admin_widget", "position_config", "right")


@pytest.mark.asyncio
@patch("app.ui.dashboard.update_widget_setting")
@patch("app.ui.dashboard._get_ordered_widgets")
@patch("app.ui.dashboard._render_layout_editor")
async def test_layout_update_missing_keys(mock_render, mock_get_ordered, mock_update_setting):
    from app.ui.dashboard import layout_update

    # 1. Completely empty form payload
    mock_req = MagicMock()
    mock_req.form = AsyncMock(return_value={})
    mock_get_ordered.return_value = []
    mock_render.return_value = Div("Mocked Layout Editor")

    # This should default scope to SCOPE_PUBLIC (0), and field is None, returning "Unknown field"
    resp = await layout_update(mock_req)
    assert "Unknown field" in str(resp)
    mock_update_setting.assert_not_called()

    # 2. Missing field key, but ext and widget exist
    mock_req_missing_field = MagicMock()
    mock_req_missing_field.form = AsyncMock(
        return_value={"ext": "test_ext", "widget": "guild_admin_widget", "scope_id": "2"}
    )
    resp = await layout_update(mock_req_missing_field)
    assert "Unknown field" in str(resp)
    mock_update_setting.assert_not_called()


@pytest.mark.asyncio
async def test_layout_update_malformed_scope_id():
    from app.ui.dashboard import layout_update

    mock_req = MagicMock()
    mock_req.form = AsyncMock(
        return_value={
            "ext": "test_ext",
            "widget": "guild_admin_widget",
            "field": "position_config",
            "value": "right",
            "scope_id": "malformed_string",
        }
    )
    # scope_id of "malformed_string" should raise ValueError
    with pytest.raises(ValueError):
        await layout_update(mock_req)


@pytest.mark.asyncio
async def test_layout_update_column_span_non_integer():
    from app.ui.dashboard import layout_update

    mock_req = MagicMock()
    mock_req.form = AsyncMock(
        return_value={
            "ext": "test_ext",
            "widget": "guild_admin_widget",
            "field": "column_span",
            "value": "not_an_int",
            "scope_id": "2",
        }
    )
    # value of "not_an_int" for column_span should raise ValueError
    with pytest.raises(ValueError):
        await layout_update(mock_req)


@pytest.mark.asyncio
@patch("app.ui.dashboard.update_widget_setting")
@patch("app.ui.dashboard._get_ordered_widgets")
@patch("app.ui.dashboard._render_layout_editor")
async def test_layout_update_column_span_extreme_values(mock_render, mock_get_ordered, mock_update_setting):
    from app.ui.dashboard import layout_update

    # Value is extremely large integer
    mock_req = MagicMock()
    mock_req.form = AsyncMock(
        return_value={
            "ext": "test_ext",
            "widget": "guild_admin_widget",
            "field": "column_span",
            "value": "999999999",
            "scope_id": "2",
        }
    )
    mock_get_ordered.return_value = []
    mock_render.return_value = Div("Mocked Layout Editor")

    await layout_update(mock_req)
    mock_update_setting.assert_called_once_with(2, "test_ext", "guild_admin_widget", "column_span", 999999999)


@pytest.mark.asyncio
@patch("app.ui.dashboard.update_widget_setting")
@patch("app.ui.dashboard._get_ordered_widgets")
@patch("app.ui.dashboard._render_layout_editor")
async def test_layout_update_position_config_arbitrary_values(mock_render, mock_get_ordered, mock_update_setting):
    from app.ui.dashboard import layout_update

    # Check that any arbitrary string is accepted and sent to the database helper
    mock_req = MagicMock()
    mock_req.form = AsyncMock(
        return_value={
            "ext": "test_ext",
            "widget": "guild_admin_widget",
            "field": "position_config",
            "value": "arbitrary_unsafe_value_xyz",
            "scope_id": "2",
        }
    )
    mock_get_ordered.return_value = []
    mock_render.return_value = Div("Mocked Layout Editor")

    await layout_update(mock_req)
    mock_update_setting.assert_called_once_with(
        2, "test_ext", "guild_admin_widget", "position_config", "arbitrary_unsafe_value_xyz"
    )


def test_render_layout_editor_invalid_position_config():
    # Verify that a widget with an invalid position_config defaults to "Grid Layout" and has reorder buttons
    widgets = [
        {
            "ext": "test_ext",
            "widget": "guild_admin_widget_1",
            "enabled": True,
            "span": 4,
            "order": 1,
            "position_config": "invalid_position_config_here",
        }
    ]
    from app.ui.dashboard import _render_layout_editor

    rendered = _render_layout_editor(widgets, 2)
    html = str(rendered)

    # 1. Verify it renders "Grid"
    assert "Grid" in html

    # 2. Verify it has the up/down reorder buttons because is_fixed_or_floating is False
    assert "fa-solid fa-arrow-up" in html
    assert "fa-solid fa-arrow-down" in html


@pytest.mark.asyncio
@patch("app.ui.dashboard.update_widget_setting")
@patch("app.ui.dashboard._get_ordered_widgets")
@patch("app.ui.dashboard._render_layout_editor")
async def test_layout_move_fixed_or_floating_widget(mock_render, mock_get_ordered, mock_update_setting):
    from app.ui.dashboard import layout_move

    # We mock _get_ordered_widgets to return a list of widgets, where index 0 is fixed
    mock_get_ordered.return_value = [
        {"ext": "ext1", "widget": "fixed_w", "enabled": True, "span": 4, "order": 0, "position_config": "left"},
        {"ext": "ext2", "widget": "grid_w", "enabled": True, "span": 4, "order": 1, "position_config": None},
    ]
    mock_render.return_value = Div("Mocked Layout Editor")

    mock_req = MagicMock()
    mock_req.form = AsyncMock(return_value={"ext": "ext1", "widget": "fixed_w", "direction": "down", "scope_id": "2"})

    await layout_move(mock_req)

    # Verify that even though fixed_w is fixed, the backend still swapped it
    # and updated the display_order setting for both widgets in the database.
    # The new order should have grid_w at order 0, and fixed_w at order 1.
    assert mock_update_setting.call_count == 2
    mock_update_setting.assert_any_call(2, "ext1", "fixed_w", "display_order", 1)
    mock_update_setting.assert_any_call(2, "ext2", "grid_w", "display_order", 0)


@pytest.mark.asyncio
@patch("app.ui.dashboard.update_widget_setting")
@patch("app.ui.dashboard._get_ordered_widgets")
@patch("app.ui.dashboard._render_layout_editor")
async def test_layout_update_sql_injection_attempt(mock_render, mock_get_ordered, mock_update_setting):
    from app.ui.dashboard import layout_update

    mock_req = MagicMock()
    mock_req.form = AsyncMock(
        return_value={
            "ext": "test_ext",
            "widget": "guild_admin_widget",
            "field": "position_config",
            "value": "'; DROP TABLE widget_settings; --",
            "scope_id": "2",
        }
    )
    mock_get_ordered.return_value = []
    mock_render.return_value = Div("Mocked Layout Editor")

    await layout_update(mock_req)
    mock_update_setting.assert_called_once_with(
        2, "test_ext", "guild_admin_widget", "position_config", "'; DROP TABLE widget_settings; --"
    )


@pytest.mark.asyncio
@patch("app.ui.dashboard.update_widget_setting")
@patch("app.ui.dashboard._get_ordered_widgets")
@patch("app.ui.dashboard._render_layout_editor")
async def test_layout_update_null_byte_value(mock_render, mock_get_ordered, mock_update_setting):
    from app.ui.dashboard import layout_update

    mock_req = MagicMock()
    mock_req.form = AsyncMock(
        return_value={
            "ext": "test_ext\x00",
            "widget": "guild_admin_widget\x00",
            "field": "position_config",
            "value": "right\x00",
            "scope_id": "2",
        }
    )
    mock_get_ordered.return_value = []
    mock_render.return_value = Div("Mocked Layout Editor")

    await layout_update(mock_req)
    mock_update_setting.assert_called_once_with(
        2, "test_ext\x00", "guild_admin_widget\x00", "position_config", "right\x00"
    )


def test_dashboard_page_with_provisioned_widgets(session):
    """Verify that DashboardPage renders sidebar/corner widgets correctly when provisioned from the DB."""
    from sqlmodel import select

    from app.db.models import WidgetSettings
    from app.ui.helpers import update_guild_extension_setting

    guild_id = 900001
    extension_name = "utilities"

    # Patch init_connection_engine for both page rendering and widget updating
    with (
        patch("app.ui.helpers.init_connection_engine", return_value=session.get_bind()),
        patch("app.common.alchemy.init_connection_engine", return_value=session.get_bind()),
    ):
        # Provision the default widgets in the database
        update_guild_extension_setting(
            guild_id=guild_id,
            extension_name=extension_name,
            gadget_type="widget",
            is_enabled=True,
        )

        # Retrieve the provisioned WidgetSettings from the database
        widgets = session.exec(
            select(WidgetSettings).where(
                WidgetSettings.guild_id == guild_id,
                WidgetSettings.extension_name == extension_name,
            )
        ).all()

        assert len(widgets) == 8

        # Separate fixed and floating widgets based on their position_config
        fixed_widgets = []
        floating_widgets = []
        for w in widgets:
            if w.position_config in ("left", "right"):
                comp = Div(f"Component: {w.widget_name}", id=w.widget_name)
                comp.position_config = w.position_config
                fixed_widgets.append(comp)
            elif w.position_config in ("bottom-right", "bottom-left", "top-right", "top-left"):
                comp = Div(f"Component: {w.widget_name}", id=w.widget_name)
                comp.position_config = w.position_config
                floating_widgets.append(comp)

        # Call DashboardPage
        title, div = DashboardPage(
            "Dashboard Page layout test",
            Div("Dashboard content"),
            guild_id=guild_id,
            fixed_widgets=fixed_widgets,
            floating_widgets=floating_widgets,
        )

    html = str(div)

    # Verify that the generated HTML has the correct margin classes
    assert "margin-left: 312px;" in html
    assert "margin-right: 312px;" not in html

    # Verify that it includes specific sidebar and corner elements
    assert "guild_admin_utilities_sidebar" in html
    assert "guild_admin_utilities_help_bubble" in html


def test_dashboard_page_fixed_sidebar_rendering_margins_isolated():
    """Verify fixed sidebar rendering margins under different sidebar configurations."""
    # If only a left sidebar is active
    left_w = Div("Left Widget")
    left_w.position_config = "left"
    _, div_left = DashboardPage("Title", Div("Content"), fixed_widgets=[left_w])
    html_left = str(div_left)
    assert "margin-left: 312px;" in html_left
    assert "margin-right: 312px;" not in html_left

    # If only a right sidebar is active
    right_w = Div("Right Widget")
    right_w.position_config = "right"
    _, div_right = DashboardPage("Title", Div("Content"), fixed_widgets=[right_w])
    html_right = str(div_right)
    assert "margin-right: 312px;" in html_right
    assert "margin-left: 312px;" not in html_right

    # If both are active
    _, div_both = DashboardPage("Title", Div("Content"), fixed_widgets=[left_w, right_w])
    html_both = str(div_both)
    assert "margin-left: 312px;" in html_both
    assert "margin-right: 312px;" in html_both

    # If neither is active
    _, div_neither = DashboardPage("Title", Div("Content"), fixed_widgets=[])
    html_neither = str(div_neither)
    assert "margin-left: 312px;" not in html_neither
    assert "margin-right: 312px;" not in html_neither


def test_dashboard_page_floating_widgets_all_corners_isolated():
    """Verify floating widgets rendering in all 4 corners and checking style properties."""
    floating_widgets = [
        Div("Bottom Right", position_config="bottom-right"),
        Div("Bottom Left", position_config="bottom-left"),
        Div("Top Right", position_config="top-right"),
        Div("Top Left", position_config="top-left"),
    ]
    _, div = DashboardPage("Title", Div("Content"), floating_widgets=floating_widgets)
    html = str(div)
    assert 'style="position: fixed; z-index: 50; bottom: 20px; right: 20px;"' in html
    assert 'style="position: fixed; z-index: 50; bottom: 20px; left: 20px;"' in html
    assert 'style="position: fixed; z-index: 50; top: 100px; right: 20px;"' in html
    assert 'style="position: fixed; z-index: 50; top: 100px; left: 20px;"' in html


@pytest.mark.asyncio
async def test_dashboard_auto_provisioning_on_first_load(session):
    """Verify auto-provisioning of default widgets on first load of a newly configured guild dashboard."""
    from sqlmodel import select

    from app.db.models import GuildExtensionSettings, WidgetSettings
    from app.ui.dashboard import dashboard

    guild_id = 999123
    extension_name = "utilities"

    mock_client = AsyncMock()
    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"roles": []}
    mock_client.get.return_value = mock_resp

    try:
        with (
            patch("app.ui.helpers.init_connection_engine", return_value=session.get_bind()),
            patch("app.common.alchemy.init_connection_engine", return_value=session.get_bind()),
            patch("app.ui.dashboard.get_admin_guilds", return_value={str(guild_id): {"name": "Test Server"}}),
            patch("app.ui.dashboard.get_internal_api_client", return_value=mock_client_cls),
        ):
            # Create global setting enabling the widget extension
            global_setting = GuildExtensionSettings(
                guild_id=0, extension_name=extension_name, gadget_type="widget", is_enabled=True
            )
            session.add(global_setting)
            session.commit()

            # Check that WidgetSettings is currently empty for this guild
            existing_settings = session.exec(select(WidgetSettings).where(WidgetSettings.guild_id == guild_id)).all()
            assert len(existing_settings) == 0

            # Commit/release any active transaction locks on the test session before calling the endpoint
            session.commit()

            # Call dashboard router function (representing first load)
            sess = {"auth": {"id": "12345", "token_data": {"access_token": "dummy_token"}}}
            await dashboard(guild_id, sess)

            # Retrieve the newly provisioned WidgetSettings from the database
            widgets = session.exec(
                select(WidgetSettings).where(
                    WidgetSettings.guild_id == guild_id,
                    WidgetSettings.extension_name == extension_name,
                )
            ).all()

            # Verify all default widgets are provisioned
            widget_names = {w.widget_name for w in widgets}

            expected_widgets = {
                "guild_admin_security_overview_widget",
                "guild_admin_alerts_widget",
                "guild_admin_auditor_settings_widget",
                "guild_admin_audit_roles_widget",
                "guild_admin_audit_channels_widget",
                "guild_admin_audit_permissions_widget",
                "guild_admin_utilities_sidebar",
                "guild_admin_utilities_help_bubble",
            }

            for ew in expected_widgets:
                assert ew in widget_names

            assert len(widgets) == 8
    finally:
        from sqlmodel import delete

        session.exec(delete(WidgetSettings).where(WidgetSettings.guild_id == guild_id))
        session.exec(delete(GuildExtensionSettings).where(GuildExtensionSettings.guild_id == guild_id))
        session.exec(delete(GuildExtensionSettings).where(GuildExtensionSettings.guild_id == 0))
        session.commit()


@pytest.mark.asyncio
async def test_restore_default_widget_settings(session):
    """Verify restore_default_widget_settings resets a guild's widgets to manifest defaults."""
    from sqlmodel import select

    from app.db.models import GuildExtensionSettings, WidgetSettings
    from app.ui.helpers import restore_default_widget_settings

    guild_id = 999124
    extension_name = "utilities"

    try:
        with (
            patch("app.ui.helpers.init_connection_engine", return_value=session.get_bind()),
            patch("app.common.alchemy.init_connection_engine", return_value=session.get_bind()),
        ):
            # 1. Enable extension globally
            global_setting = GuildExtensionSettings(
                guild_id=0, extension_name=extension_name, gadget_type="widget", is_enabled=True
            )
            session.add(global_setting)
            session.commit()

            # 2. Insert customized layout widget settings for guild
            custom_widget = WidgetSettings(
                guild_id=guild_id,
                extension_name=extension_name,
                widget_name="guild_admin_security_overview_widget",
                is_enabled=False,  # default is True
                display_order=12,  # custom
                column_span=8,  # custom
            )
            session.add(custom_widget)
            session.commit()

            # 3. Call restore default widget settings
            restore_default_widget_settings(guild_id)

            # 4. Assert that customized setting was reset to default
            restored = session.exec(
                select(WidgetSettings).where(
                    WidgetSettings.guild_id == guild_id,
                    WidgetSettings.widget_name == "guild_admin_security_overview_widget",
                )
            ).first()

            assert restored is not None
            assert restored.is_enabled is True
            assert restored.column_span == 4  # default from manifest

    finally:
        from sqlmodel import delete

        session.exec(delete(WidgetSettings).where(WidgetSettings.guild_id == guild_id))
        session.exec(delete(GuildExtensionSettings).where(GuildExtensionSettings.guild_id == guild_id))
        session.exec(delete(GuildExtensionSettings).where(GuildExtensionSettings.guild_id == 0))
        session.commit()


@pytest.mark.asyncio
@patch("app.ui.dashboard._render_layout_editor")
@patch("app.ui.dashboard._get_ordered_widgets")
@patch("app.ui.helpers.restore_default_widget_settings")
async def test_layout_restore_route(mock_restore, mock_get_ordered, mock_render):
    """Verify that layout_restore route calls restore function and renders the layout editor."""
    from app.ui.dashboard import layout_restore

    mock_req = AsyncMock()
    mock_req.form.return_value = {"scope_id": "999124"}
    mock_render.return_value = Div("Mocked Layout Editor")

    resp = await layout_restore(mock_req)

    mock_restore.assert_called_once_with(999124)
    mock_get_ordered.assert_called_once_with(999124)
    mock_render.assert_called_once()
    assert str(resp) == "<div>Mocked Layout Editor</div>"


@pytest.mark.asyncio
async def test_get_rules_info():
    """Verify that get_rules_info returns the modal with the 8 security rules."""
    from fasthtml.common import to_xml

    from app.ui.dashboard import get_rules_info
    resp = await get_rules_info(guild_id=12345)
    html = to_xml(resp)
    assert "Security Rules Reference" in html
    assert "Category Permission Baseline" in html
    assert "Public Announcement Protection" in html
    assert "Exposed Staff Channels" in html
    assert "Unauthorized Chat Pings in Non-Text Locations" in html
    assert "Low-Tier Role Privileges" in html
    assert "General Role Mentionability" in html
    assert "Suggestive Honeypot Integration" in html
    assert "Over-privileged Bot Integrations" in html

