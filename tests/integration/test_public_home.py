import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fasthtml.common import Div, to_xml

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.main_ui import public_home  # noqa: E402

# All tests in this module are integration tests.
pytestmark = pytest.mark.integration


@pytest.fixture
def mock_session():
    return {"auth": None}


@patch("app.main_ui.GadgetInspector")
@patch("app.main_ui.get_widget_settings")
@patch("app.main_ui.get_widget_name")
@patch("app.main_ui.get_guild_sprockets")
@patch("app.main_ui.is_gadget_enabled")
def test_public_home_respects_global_settings(
    mock_is_enabled, mock_get_sprockets, mock_get_name, mock_get_settings, mock_inspector, mock_session
):
    # Setup
    mock_inspector_instance = MagicMock()
    # Mock a widget function
    mock_widget_func = MagicMock()
    # The widget function returns a component
    mock_widget_func.return_value = Div("Widget Content")

    # inspect_widgets returns {ext_name: [widget_funcs]}
    mock_inspector_instance.inspect_widgets.return_value = {"test_ext": [mock_widget_func]}
    mock_inspector.return_value = mock_inspector_instance

    mock_get_name.return_value = "TestWidget"

    # Mock settings: Enabled in layout
    mock_get_settings.return_value = {"TestWidget": {"is_enabled": True, "display_order": 1, "column_span": 4}}

    # Mock enabled sprockets default to empty
    mock_get_sprockets.return_value = []

    # CASE 1: Extension is GLOBALLY DISABLED
    # is_gadget_enabled(0, "test_ext", "widget") -> False
    mock_is_enabled.return_value = False

    component = public_home(mock_session)
    html = to_xml(component)

    assert "Widget Content" not in html
    assert "API Docs" not in html

    # Verify is_gadget_enabled was called with (0, "test_ext", "widget")
    mock_is_enabled.assert_called_with(0, "test_ext", "widget")

    # CASE 2: Extension is GLOBALLY ENABLED
    mock_is_enabled.return_value = True

    component = public_home(mock_session)
    html = to_xml(component)

    assert "Widget Content" in html
    assert "API Docs" not in html  # Still no sprockets

    # CASE 3: Sprockets Enabled
    mock_get_sprockets.return_value = ["test_ext"]

    component = public_home(mock_session)
    html = to_xml(component)

    assert "API Docs" not in html
    assert "http://localhost:8000/docs" not in html
