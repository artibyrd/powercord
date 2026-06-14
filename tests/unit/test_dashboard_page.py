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
from app.ui.page import DashboardPage, SideNavBar, TopAppBar

pytestmark = pytest.mark.unit


def test_dashboard_page_rendering():
    """Verify that DashboardPage renders sidebar and navbar correctly with defaults."""
    title, div = DashboardPage("My Test title", Div("Hello World"))
    assert "My Test title" in str(title)

    html = str(div)
    # Check that SideNavBar and TopAppBar are rendered (based on defaults show_sidebar=True, show_topbar=True)
    assert "Powercord" in html
    assert "Dashboard Home" in html
    assert "Hello World" in html


def test_top_app_bar():
    """Verify TopAppBar outputs correct branding and lockdown button when guild_id is provided."""
    top_bar = TopAppBar(auth=None, guild_id=98765)
    html = str(top_bar)
    assert "Powercord" in html
    assert "Server: 98765" in html
    assert "Lockdown" in html


def test_side_nav_bar():
    """Verify SideNavBar includes correct paths."""
    side_bar = SideNavBar(guild_id=12345)
    html = str(side_bar)
    assert "/dashboard/12345" in html
    assert "/dashboard/12345/alerts" in html
    assert "/dashboard/12345/inspect" in html
    assert "/dashboard/12345/settings" in html


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
        req.query_params = {"show_sidebar": "false", "show_topbar": "false"}
        req.form = AsyncMock(return_value={})

        resp = await toggle_nav_route(guild_id=12345, req=req, sess=sess)

        # Verify it returns HX-Refresh header
        assert isinstance(resp, Response)
        assert resp.headers.get("HX-Refresh") == "true"

        # Verify db interaction
        mock_session_obj.add.assert_called_once()
        mock_session_obj.commit.assert_called_once()

        # Verify it set show_sidebar and show_topbar to False
        added_obj = mock_session_obj.add.call_args[0][0]
        assert added_obj.user_id == 12345
        assert added_obj.show_sidebar is False
        assert added_obj.show_topbar is False
