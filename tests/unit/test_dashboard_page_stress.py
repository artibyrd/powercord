# ruff: noqa: E402
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fasthtml.common import Div

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.ui.page import DashboardPage

pytestmark = pytest.mark.unit


def test_guild_name_edge_cases():
    """Verify guild_name handles empty string, None, special characters, and long strings."""
    # 1. None (should fallback to Server: 123)
    _, div_none = DashboardPage("Title", guild_id=123, guild_name=None)
    html_none = str(div_none)
    assert "Server: 123" in html_none

    # 2. Empty string
    _, div_empty = DashboardPage("Title", guild_id=123, guild_name="")
    html_empty = str(div_empty)
    assert "Server: 123" not in html_empty
    assert '<span class="font-semibold text-sm"></span>' in html_empty

    # 3. Special characters (checking HTML escaping)
    special = "<script>alert('hack')</script> & \"bar\""
    _, div_special = DashboardPage("Title", guild_id=123, guild_name=special)
    html_special = str(div_special)
    assert "&lt;script&gt;alert(&#x27;hack&#x27;)&lt;/script&gt; &amp; &quot;bar&quot;" in html_special

    # 4. Extremely long string
    long_name = "A" * 10000
    _, div_long = DashboardPage("Title", guild_id=123, guild_name=long_name)
    html_long = str(div_long)
    assert long_name in html_long


def test_widget_parameters_robustness():
    """Verify that fixed_widgets and floating_widgets do not crash when they are provided, omitted, empty, or contain malformed widgets."""

    # 1. Omitted / None
    _, div_omitted = DashboardPage("Title")
    html_omitted = str(div_omitted)
    assert "margin-left:" not in html_omitted
    assert "margin-right:" not in html_omitted

    # 2. Empty lists
    _, div_empty = DashboardPage("Title", fixed_widgets=[], floating_widgets=[])
    html_empty = str(div_empty)
    assert "margin-left:" not in html_empty
    assert "margin-right:" not in html_empty

    # 3. None elements in lists
    _, div_nones = DashboardPage("Title", fixed_widgets=[None, None], floating_widgets=[None, None])
    html_nones = str(div_nones)
    assert "margin-left:" not in html_nones
    assert "margin-right:" not in html_nones

    # 4. Malformed widgets (dict missing 'component' or 'position_config')
    w_missing_comp = {"position_config": "right"}
    w_missing_pos = {"component": Div("Missing Pos", id="missing-pos")}
    w_empty_dict = {}

    _, div_malformed_dict = DashboardPage(
        "Title",
        fixed_widgets=[w_missing_comp, w_missing_pos, w_empty_dict],
        floating_widgets=[w_missing_comp, w_missing_pos, w_empty_dict]
    )
    html_malformed = str(div_malformed_dict)

    # w_missing_pos should default to left fixed sidebar
    assert "margin-left: 280px;" in html_malformed
    assert "margin-right: 280px;" not in html_malformed  # w_missing_comp is skipped because no component
    assert "Missing Pos" in html_malformed

    # 5. Malformed widgets (objects missing 'position_config' attribute)
    class DummyWidget:
        def __init__(self, name):
            self.name = name
        def __ft__(self):
            return Div(self.name, id=self.name)

    dummy_obj = DummyWidget("dummy-obj")
    _, div_obj = DashboardPage("Title", fixed_widgets=[dummy_obj])
    html_obj = str(div_obj)
    # Should default to left fixed since pos is None (not "right")
    assert "margin-left: 280px;" in html_obj
    assert "dummy-obj" in html_obj

    # 6. Malformed widgets with invalid position_config values
    w_invalid_pos_fixed = {"component": Div("Invalid Fixed", id="invalid-fixed"), "position_config": "invalid-side"}
    w_invalid_pos_float = {"component": Div("Invalid Float", id="invalid-float"), "position_config": "invalid-corner"}

    _, div_invalid_pos = DashboardPage(
        "Title",
        fixed_widgets=[w_invalid_pos_fixed],
        floating_widgets=[w_invalid_pos_float]
    )
    html_invalid = str(div_invalid_pos)

    # Fixed widget with invalid position defaults to left fixed
    assert "margin-left: 280px;" in html_invalid
    assert "Invalid Fixed" in html_invalid

    # Floating widget with invalid position defaults to bottom-right (bottom: 20px; right: 20px;)
    assert 'style="position: fixed; z-index: 50; bottom: 20px; right: 20px;"' in html_invalid
    assert "Invalid Float" in html_invalid


def test_multiple_widgets_margin_shifting():
    """Verify that multiple fixed widgets on the same or opposite sides do not crash or cause double margin shift."""
    w1 = {"component": Div("W1"), "position_config": "left"}
    w2 = {"component": Div("W2"), "position_config": "left"}
    w3 = {"component": Div("W3"), "position_config": "right"}
    w4 = {"component": Div("W4"), "position_config": "right"}

    # Multiple on left side
    _, div_left_multi = DashboardPage("Title", fixed_widgets=[w1, w2])
    html_left_multi = str(div_left_multi)
    # Should only shift once (280px)
    assert "margin-left: 280px;" in html_left_multi
    # Should not have multiple margin-left shifts
    assert html_left_multi.count("margin-left: 280px;") == 1
    assert "margin-right: 280px;" not in html_left_multi

    # Multiple on opposite sides
    _, div_both_multi = DashboardPage("Title", fixed_widgets=[w1, w2, w3, w4])
    html_both_multi = str(div_both_multi)
    assert "margin-left: 280px;" in html_both_multi
    assert "margin-right: 280px;" in html_both_multi
    assert html_both_multi.count("margin-left: 280px;") == 1
    assert html_both_multi.count("margin-right: 280px;") == 1


def test_type_error_crashes():
    """Test that passing non-iterable types to widgets parameters results in a TypeError (or logical anomaly)."""
    # Passing an integer raises TypeError
    with pytest.raises(TypeError):
        DashboardPage("Title", fixed_widgets=123)

    with pytest.raises(TypeError):
        DashboardPage("Title", floating_widgets=123)

    # Passing a string leads to logical anomalies (treating chars as components)
    _, div_string = DashboardPage("Title", fixed_widgets="abc")
    html_string = str(div_string)
    # It loops over 'a', 'b', 'c', appends them as components in left fixed sidebar
    assert "margin-left: 280px;" in html_string
    # FastHTML parses strings as children directly, resulting in 'a', 'b', 'c' being rendered
    assert "a" in html_string
    assert "b" in html_string
    assert "c" in html_string


# ==============================================================================
# ADVERSARIAL & STRESS TESTS FOR LAYOUT RENDERING
# ==============================================================================

def test_layout_rendering_dozens_of_sidebars():
    """Verify performance and correct rendering with large numbers of widgets."""
    left_widgets = [
        {"component": Div(f"Left Widget {i}", id=f"left-w-{i}"), "position_config": "left"}
        for i in range(100)
    ]
    right_widgets = [
        {"component": Div(f"Right Widget {i}", id=f"right-w-{i}"), "position_config": "right"}
        for i in range(100)
    ]
    floating_widgets = [
        {"component": Div(f"Float Widget {i}", id=f"float-w-{i}"), "position_config": "bottom-left"}
        for i in range(100)
    ]

    start_time = time.perf_counter()
    _, div = DashboardPage(
        "Dozens Title",
        Div("Content"),
        fixed_widgets=left_widgets + right_widgets,
        floating_widgets=floating_widgets
    )
    html = str(div)
    duration = time.perf_counter() - start_time

    # Render layout should be extremely fast (typically < 100ms)
    assert duration < 0.2

    # Check margins are only applied once in style attributes
    assert "margin-left: 280px;" in html
    assert "margin-right: 280px;" in html
    assert html.count("margin-left: 280px;") == 1
    assert html.count("margin-right: 280px;") == 1

    # Verify all widgets are in the output HTML
    for i in range(100):
        assert f"Left Widget {i}" in html
        assert f"Right Widget {i}" in html
        assert f"Float Widget {i}" in html


def test_layout_rendering_malformed_coordinates_and_objects():
    """Verify that malformed position configs and abnormal objects default gracefully."""
    class PoisonWidget:
        @property
        def position_config(self):
            raise AttributeError("Poison attribute access!")
        def __ft__(self):
            return Div("Poison Component")

    w_none_component = {"component": None, "position_config": "left"}
    w_non_string_pos = {"component": Div("Non-string pos"), "position_config": 99999}
    w_empty_list_pos = {"component": Div("List pos"), "position_config": ["left"]}
    w_none_pos = {"component": Div("None pos"), "position_config": None}

    # Verify we can pass these without crashing
    _, div = DashboardPage(
        "Malformed Test",
        Div("Main"),
        fixed_widgets=[PoisonWidget(), w_none_component, w_non_string_pos, w_empty_list_pos, w_none_pos],
        floating_widgets=[{"component": Div("Float None pos"), "position_config": None}, None]
    )
    html = str(div)

    # Assert they default gracefully to left fixed / bottom-right float
    assert "Poison Component" in html
    assert "Non-string pos" in html
    assert "List pos" in html
    assert "None pos" in html
    assert "Float None pos" in html
    assert "margin-left: 280px;" in html
    assert 'style="position: fixed; z-index: 50; bottom: 20px; right: 20px;"' in html


def test_layout_rendering_extremely_large_strings():
    """Verify that layout rendering handles extremely large strings without crashing."""
    huge_guild_name = "Guild" + "X" * 200000
    huge_title = "Title" + "Y" * 200000
    huge_content = "Content" + "Z" * 500000

    large_widget = {"component": Div(huge_content), "position_config": "right"}

    start = time.perf_counter()
    title_res, div_res = DashboardPage(
        huge_title,
        Div("Main"),
        guild_name=huge_guild_name,
        guild_id=12345,
        fixed_widgets=[large_widget]
    )
    html = str(div_res)
    duration = time.perf_counter() - start

    assert duration < 0.5
    assert huge_guild_name in html
    assert huge_title in str(title_res)
    assert huge_content in html


# ==============================================================================
# AUTO-PROVISIONING LOGIC ROBUSTNESS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_auto_provisioning_sequential_requests(session, engine):
    """Verify that sequential loads of the dashboard starting from empty DB states:
    1. Initialize the default widgets exactly once on the first load.
    2. Do not duplicate widgets on subsequent loads.
    3. Do not overwrite custom settings changed by the user.
    """
    from sqlmodel import select

    from app.db.models import GuildExtensionSettings, WidgetSettings
    from app.ui.dashboard import dashboard
    from app.ui.helpers import update_widget_setting

    guild_id = 999991
    extension_name = "utilities"
    sess = {"auth": {"id": "12345", "token_data": {"access_token": "dummy_token"}}}

    try:
        # Patch init_connection_engine to point to our test DB connection
        with patch("app.ui.helpers.init_connection_engine", return_value=engine), \
             patch("app.common.alchemy.init_connection_engine", return_value=engine), \
             patch("app.ui.dashboard.get_admin_guilds", return_value={str(guild_id): {"name": "Test Server"}}):

            # Enable widget globally
            global_setting = GuildExtensionSettings(
                guild_id=0,
                extension_name=extension_name,
                gadget_type="widget",
                is_enabled=True
            )
            session.add(global_setting)
            session.commit()

            # Verify initially no widget settings exist for this guild
            assert len(session.exec(select(WidgetSettings).where(WidgetSettings.guild_id == guild_id)).all()) == 0

            # 1. First load: triggers auto-provisioning
            await dashboard(guild_id, sess)
            session.expire_all()

            widgets_after_first = session.exec(
                select(WidgetSettings).where(
                    WidgetSettings.guild_id == guild_id,
                    WidgetSettings.extension_name == extension_name
                )
            ).all()
            assert len(widgets_after_first) == 8

            # 2. Modify one widget setting (disable guild_admin_alerts)
            target_widget = "guild_admin_alerts"
            update_widget_setting(guild_id, extension_name, target_widget, "is_enabled", False)
            session.expire_all()

            # Verify the modification in the database
            db_widget = session.exec(
                select(WidgetSettings).where(
                    WidgetSettings.guild_id == guild_id,
                    WidgetSettings.widget_name == target_widget
                )
            ).one()
            assert db_widget.is_enabled is False

            # 3. Second load: must not duplicate settings or overwrite modifications
            await dashboard(guild_id, sess)
            session.expire_all()

            widgets_after_second = session.exec(
                select(WidgetSettings).where(
                    WidgetSettings.guild_id == guild_id,
                    WidgetSettings.extension_name == extension_name
                )
            ).all()
            assert len(widgets_after_second) == 8

            db_widget_after = session.exec(
                select(WidgetSettings).where(
                    WidgetSettings.guild_id == guild_id,
                    WidgetSettings.widget_name == target_widget
                )
            ).one()
            assert db_widget_after.is_enabled is False

    finally:
        # Proper cleanup of any database mutations in finally block
        from sqlmodel import delete
        session.exec(delete(WidgetSettings).where(WidgetSettings.guild_id == guild_id))
        session.exec(delete(GuildExtensionSettings).where(GuildExtensionSettings.guild_id == guild_id))
        session.exec(delete(GuildExtensionSettings).where(GuildExtensionSettings.guild_id == 0))
        session.commit()


def test_auto_provisioning_sequential_extension_updates(session, engine):
    """Verify that sequential calls to update_guild_extension_setting:
    1. Do not create duplicate GuildExtensionSettings entries.
    2. Do not create duplicate WidgetSettings entries.
    3. Behave correctly when transitioning enabled -> disabled -> enabled.
    """
    from sqlmodel import select

    from app.db.models import GuildExtensionSettings, WidgetSettings
    from app.ui.helpers import update_guild_extension_setting

    guild_id = 999992
    extension_name = "utilities"

    try:
        with patch("app.ui.helpers.init_connection_engine", return_value=engine), \
             patch("app.common.alchemy.init_connection_engine", return_value=engine):

            # Enable the extension: first time
            update_guild_extension_setting(guild_id, extension_name, "widget", True)
            session.expire_all()

            # Assert single entry in GuildExtensionSettings and 8 widgets in WidgetSettings
            ext_settings = session.exec(
                select(GuildExtensionSettings).where(
                    GuildExtensionSettings.guild_id == guild_id,
                    GuildExtensionSettings.extension_name == extension_name,
                    GuildExtensionSettings.gadget_type == "widget"
                )
            ).all()
            assert len(ext_settings) == 1
            assert ext_settings[0].is_enabled is True

            widgets = session.exec(
                select(WidgetSettings).where(
                    WidgetSettings.guild_id == guild_id,
                    WidgetSettings.extension_name == extension_name
                )
            ).all()
            assert len(widgets) == 8

            # Enable again (idempotency check)
            update_guild_extension_setting(guild_id, extension_name, "widget", True)
            session.expire_all()

            # Ensure no duplication occurred
            ext_settings = session.exec(
                select(GuildExtensionSettings).where(
                    GuildExtensionSettings.guild_id == guild_id,
                    GuildExtensionSettings.extension_name == extension_name
                )
            ).all()
            assert len(ext_settings) == 1
            assert len(session.exec(select(WidgetSettings).where(WidgetSettings.guild_id == guild_id)).all()) == 8

            # Disable the extension
            update_guild_extension_setting(guild_id, extension_name, "widget", False)
            session.expire_all()

            # Ensure disabled and WidgetSettings are cleaned up
            ext_settings = session.exec(
                select(GuildExtensionSettings).where(
                    GuildExtensionSettings.guild_id == guild_id,
                    GuildExtensionSettings.extension_name == extension_name
                )
            ).all()
            assert len(ext_settings) == 1
            assert ext_settings[0].is_enabled is False
            assert len(session.exec(select(WidgetSettings).where(WidgetSettings.guild_id == guild_id)).all()) == 0

            # Re-enable
            update_guild_extension_setting(guild_id, extension_name, "widget", True)
            session.expire_all()
            assert len(session.exec(select(WidgetSettings).where(WidgetSettings.guild_id == guild_id)).all()) == 8

    finally:
        # Proper cleanup of any database mutations in finally block
        from sqlmodel import delete
        session.exec(delete(WidgetSettings).where(WidgetSettings.guild_id == guild_id))
        session.exec(delete(GuildExtensionSettings).where(GuildExtensionSettings.guild_id == guild_id))
        session.commit()
