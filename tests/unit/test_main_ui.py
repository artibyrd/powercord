from unittest.mock import AsyncMock, patch

import pytest
from fasthtml.common import Div

from app.main_ui import profile_page

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_profile_page_rendering():
    # Emulates a session dictionary with a valid authenticated user.
    sess = {
        "auth": {
            "id": "123456",
            "username": "testuser",
            "token_data": {
                "access_token": "mock_access_token"
            }
        }
    }

    # Mock get_admin_guilds to return a list of guilds
    mock_guilds = {
        "111222333": {
            "id": "111222333",
            "name": "Test Guild 1",
            "icon": "icon_hash_1",
            "permissions": "8",
        },
        "444555666": {
            "id": "444555666",
            "name": "Test Guild 2",
            "icon": None,
            "permissions": "8",
        }
    }

    with patch("app.main_ui.get_admin_guilds", new_callable=AsyncMock) as mock_get_admin_guilds, \
         patch("app.main_ui._render_client_keys", new_callable=AsyncMock) as mock_render_client_keys:
        mock_get_admin_guilds.return_value = mock_guilds
        mock_render_client_keys.return_value = Div(id="mocked-client-keys")

        response = await profile_page(sess)
        mock_get_admin_guilds.assert_called_once_with("mock_access_token", 123456)
        mock_render_client_keys.assert_called_once_with(sess)

    html = str(response)

    # Verify server names
    assert "Test Guild 1" in html
    assert "Test Guild 2" in html

    # Verify server icons
    assert "cdn.discordapp.com/icons/111222333/icon_hash_1.png" in html
    assert "cdn.discordapp.com/embed/avatars/0.png" in html

    # Verify Configure button/link
    assert "/dashboard/111222333" in html
    assert "Configure" in html

    # Verify expected grid/flex layout CSS classes
    assert "card bg-base-300 shadow-sm border border-base-content/20 rounded-xl" in html
    assert "flex items-center justify-between gap-4 p-4" in html
    assert "flex items-center gap-3 flex-grow min-w-0" in html
    assert "rounded-full flex-shrink-0" in html
    assert "font-bold text-lg line-clamp-2" in html
    assert "btn btn-outline btn-primary btn-sm flex-shrink-0" in html
    assert "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" in html


@pytest.mark.asyncio
async def test_profile_page_rendering_empty():
    sess = {
        "auth": {
            "id": "123456",
            "username": "testuser",
            "token_data": {
                "access_token": "mock_access_token"
            }
        }
    }

    with patch("app.main_ui.get_admin_guilds", new_callable=AsyncMock) as mock_get_admin_guilds, \
         patch("app.main_ui._render_client_keys", new_callable=AsyncMock) as mock_render_client_keys:
        mock_get_admin_guilds.return_value = {}
        mock_render_client_keys.return_value = Div(id="mocked-client-keys")

        response = await profile_page(sess)

    html = str(response)
    assert "No shared admin servers found." in html
