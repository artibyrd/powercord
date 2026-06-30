import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


# ── require_admin decorator tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_require_admin_blocks_non_admin():
    """An admin route decorated with @require_admin should return 'Forbidden' for non-admin users."""
    from app.main_ui import add_admin_route

    class MockReq:
        async def form(self):
            return {"user_id": "999", "comment": "should not work"}

    sess = {"auth": {"id": "999", "username": "not_admin"}}

    with patch("app.ui.helpers.is_dashboard_admin", return_value=False):
        result = await add_admin_route(req=MockReq(), sess=sess)

    from fasthtml.common import to_xml

    html = to_xml(result)
    assert "Forbidden" in html


@pytest.mark.asyncio
async def test_require_admin_allows_admin():
    """An admin route decorated with @require_admin should proceed normally for admin users."""
    from app.main_ui import add_admin_route

    class MockReq:
        async def form(self):
            return {"user_id": "0", "comment": "test"}

    sess = {
        "auth": {
            "id": "111",
            "username": "real_admin",
            "is_dashboard_admin": True,
        }
    }

    with patch("app.ui.helpers.is_dashboard_admin", return_value=True):
        with patch("app.ui.helpers.add_dashboard_admin") as mock_add:
            with patch("app.main_ui._render_admin_list", new_callable=AsyncMock) as mock_render:
                mock_render.return_value = "Rendered List"
                result = await add_admin_route(req=MockReq(), sess=sess)

    # Should have proceeded to the actual handler logic
    mock_add.assert_called_once_with(0, "test")
    assert result == "Rendered List"


@pytest.mark.asyncio
async def test_require_admin_blocks_missing_session():
    """@require_admin should return 'Forbidden' when sess is empty (no auth)."""
    from app.main_ui import add_admin_route

    class MockReq:
        async def form(self):
            return {"user_id": "0"}

    result = await add_admin_route(req=MockReq(), sess={})

    from fasthtml.common import to_xml

    html = to_xml(result)
    assert "Forbidden" in html


# ── _check_guild_admin default-deny tests ──────────────────────────────


@pytest.mark.asyncio
async def test_check_guild_admin_denies_missing_session():
    """_check_guild_admin() should return False when session is missing, not True."""
    from app.ui.dashboard import _check_guild_admin

    req = MagicMock(spec=[])  # No session attribute at all
    result = await _check_guild_admin(123, req)
    assert result is False


@pytest.mark.asyncio
async def test_check_guild_admin_denies_none_session():
    """_check_guild_admin() should return False when session is None."""
    from app.ui.dashboard import _check_guild_admin

    req = MagicMock()
    req.session = None
    result = await _check_guild_admin(123, req)
    assert result is False


@pytest.mark.asyncio
async def test_check_guild_admin_denies_non_dict_auth():
    """_check_guild_admin() should return False when auth is not a dict."""
    from app.ui.dashboard import _check_guild_admin

    req = MagicMock()
    req.session = {"auth": "not_a_dict"}
    result = await _check_guild_admin(123, req)
    assert result is False
