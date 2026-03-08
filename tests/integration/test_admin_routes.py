# Ensure we can import from app
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.main_ui import admin_home, app  # noqa: E402

# All tests in this module are integration tests.
pytestmark = pytest.mark.integration

client = TestClient(app)  # type: ignore[arg-type]


@pytest.fixture
def mock_session():
    return {
        "auth": {
            "username": "TestUser",
            "token_data": {"access_token": "fake_token"},
            "is_dashboard_admin": True,
            "id": "123456789",
        }
    }


@patch("app.main_ui.get_admin_guilds")
@patch("app.main_ui.get_guild_cogs")
@patch("app.main_ui.get_guild_sprockets")
@patch("app.main_ui.get_guild_widgets")
@patch("app.main_ui.GadgetInspector")
def test_admin_home_extensions_section(
    mock_inspector, mock_get_widgets, mock_get_sprockets, mock_get_cogs, mock_get_guilds, mock_session
):
    # Mock data
    mock_get_guilds.return_value = {}
    mock_get_cogs.return_value = ["test_ext"]
    mock_get_sprockets.return_value = []
    mock_get_widgets.return_value = []

    mock_inspector_instance = MagicMock()
    mock_inspector_instance.inspect_extensions.return_value = {"test_ext": ["cog", "widget"]}
    mock_inspector.return_value = mock_inspector_instance

    # We can't easily use client.get("/admin") because of the session middleware and auth.
    # But we can call the route handler directly if we mock the request/session

    # However, FastHTML route handlers take specific args. admin_home takes (sess).
    # It returns a FastHTML component tree.

    import asyncio
    # admin_home is async

    component = asyncio.run(admin_home(mock_session))

    # Verify the component contains "Manage Extensions (Global)"
    # We need to traverse the component tree or convert to string (HTML)
    from fasthtml.common import to_xml

    html = to_xml(component)

    assert "Manage Extensions (Global)" in html
    assert "test_ext" in html
    assert "toggle-primary" in html
    assert "Admin Widgets" in html
    assert "bg-base-300" in html

    # Case with enabled sprocket
    mock_get_sprockets.return_value = ["test_ext"]
    mock_inspector_instance.inspect_extensions.return_value = {"test_ext": ["sprocket"]}
    component = asyncio.run(admin_home(mock_session))
    html = to_xml(component)

    assert "toggle-primary" in html


@patch("app.ui.dashboard.get_admin_guilds")
@patch("app.ui.dashboard.get_widget_settings")
@patch("app.ui.dashboard.get_guild_cogs")
@patch("app.ui.dashboard.get_guild_sprockets")
@patch("app.ui.dashboard.get_guild_widgets")
@patch("app.ui.dashboard.GadgetInspector")
def test_dashboard_extensions_section(
    mock_inspector,
    mock_get_widgets,
    mock_get_sprockets,
    mock_get_cogs,
    mock_get_settings,
    mock_get_guilds,
    mock_session,
):
    mock_get_settings.return_value = {}
    mock_get_guilds.return_value = {"123": {"id": "123", "name": "Test Guild", "icon": None}}

    # Mock global and local enabled states
    def mock_get_gadgets(guild_id):
        return ["test_ext"]

    mock_get_cogs.side_effect = mock_get_gadgets
    mock_get_sprockets.side_effect = mock_get_gadgets
    mock_get_widgets.side_effect = mock_get_gadgets

    mock_inspector_instance = MagicMock()
    mock_inspector_instance.inspect_extensions.return_value = {"test_ext": ["cog", "widget"]}
    # Mock inspect_widgets for the rest of the function
    mock_inspector_instance.inspect_widgets.return_value = {}
    mock_inspector.return_value = mock_inspector_instance

    # Mock stats response to avoid httpx error logging
    from unittest.mock import AsyncMock

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"system": {}, "bot": {}}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        import asyncio

        from app.ui.dashboard import dashboard

        # dashboard(guild_id: int, sess)
        component = asyncio.run(dashboard(123, mock_session))

        from fasthtml.common import to_xml

        html = to_xml(component)

        assert "Manage Extensions (Server)" in html
        assert "toggle-primary" in html

        # Ensure that it targets the guild-specific endpoint
        assert 'hx-post="/dashboard/123/extensions/toggle"' in html


@patch("app.main_ui._render_admin_list")
@patch("app.ui.helpers.remove_dashboard_admin")
def test_remove_admin_route(mock_remove, mock_render, mock_session):
    import asyncio

    from app.main_ui import remove_admin_route

    class MockReq:
        async def form(self):
            return {"user_id": "0"}

    mock_render.return_value = "Rendered List"

    result = asyncio.run(remove_admin_route(MockReq(), mock_session))

    mock_remove.assert_called_once_with(0)
    assert result == "Rendered List"


@patch("app.ui.helpers.get_discord_username")
@patch("app.ui.helpers.get_dashboard_admins")
def test_render_admin_list_with_zero_id(mock_get_admins, mock_get_username, mock_session):
    import asyncio
    from types import SimpleNamespace

    from fasthtml.common import to_xml

    from app.main_ui import _render_admin_list

    mock_get_admins.return_value = [SimpleNamespace(user_id=0, comment="Test User 0")]
    
    async def get_username_mock(user_id):
        return "Test Username"
        
    mock_get_username.side_effect = get_username_mock

    component = asyncio.run(_render_admin_list(mock_session))
    html = to_xml(component)

    assert 'value="0"' in html
