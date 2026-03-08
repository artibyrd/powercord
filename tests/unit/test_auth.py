import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ui.auth import (
    auth_before,
    discord_callback,
    get_bot_guild_ids,
    get_discord_creds,
    get_user_guilds,
    login,
    logout,
)

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


def test_get_discord_creds():
    """Verifies that Discord credentials can be fetched from the os environment safely."""
    with patch.dict(os.environ, {"DISCORD_CLIENT_ID": "1", "DISCORD_CLIENT_SECRET": "2", "DISCORD_TOKEN": "3"}):
        assert get_discord_creds() == ("1", "2", "3")


@pytest.mark.asyncio
async def test_auth_before():
    """Tests the middleware hook that validates user session state prior to dashboard access."""
    sess = {}
    req = MagicMock()
    req.scope = {}
    req.url.path = "/admin"

    # Missing session results in a 303 Redirect to login page
    redirect = await auth_before(req, sess)
    assert redirect.status_code == 303

    # Having "auth" key allows the request to pass cleanly if admin permissions are correct
    sess["auth"] = {"id": "123", "user": "test"}
    with patch("app.ui.helpers.is_dashboard_admin", return_value=True):
        res = await auth_before(req, sess)
        assert res is None


@patch("app.ui.auth.get_discord_creds")
def test_login_no_creds(mock_creds):
    """Ensures that missing client IDs throw a visible application error."""
    mock_creds.return_value = (None, None, None)
    req = MagicMock()
    res = login(req, {})
    # Look for the Titled('Error') message output string
    assert "Missing Client ID" in str(res)


@patch("app.ui.auth.get_discord_creds")
def test_login_with_creds(mock_creds):
    """Verifies standard login widget renders login URL properly."""
    mock_creds.return_value = ("client_id", "secret", "token")
    req = MagicMock()
    req.url.replace.return_value = "http://localhost/auth/discord/callback"
    with patch.dict(os.environ, {}, clear=True):
        res = login(req, {})
        assert "Login with Discord" in str(res)


@pytest.mark.asyncio
async def test_get_user_guilds():
    """Checks parsing of httpx request fetching user permissions from discord oauth2 endpoints."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": "1"}]
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

        guilds = await get_user_guilds("token")
        assert len(guilds) == 1
        assert guilds[0]["id"] == "1"


@pytest.mark.asyncio
async def test_get_bot_guild_ids():
    """Checks parsing of httpx request resolving bot membership."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": "1"}, {"id": "2"}]
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

        guilds = await get_bot_guild_ids("bot_token")
        assert "1" in guilds
        assert "2" in guilds


def test_logout():
    """Tests destruction of session credentials."""
    sess = {"auth": "user"}
    res = logout(sess)
    # Validate session cleared
    assert "auth" not in sess
    # Validate successful redirect back to index
    assert res.status_code == 303


@pytest.mark.asyncio
@patch("app.ui.auth.get_user_guilds")
@patch("app.ui.auth.get_bot_guild_ids")
@patch("httpx.AsyncClient")
async def test_discord_callback_success(mock_client, mock_bot_guilds, mock_user_guilds):
    """Integrates successful logic parsing: exchange for tokens via mocked httpx -> user info fetch -> user validation."""
    mock_bot_guilds.return_value = {"1"}
    # Permission integer 8 implies administrator role
    mock_user_guilds.return_value = [{"id": "1", "permissions": "8"}]

    # Mocking Token Exchange endpoint
    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {"access_token": "acc_tok"}

    # Mocking User Ident endpoint
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.json.return_value = {"id": "123", "username": "testuser"}

    mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp1)
    mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp2)

    with patch.dict(
        os.environ,
        {"DISCORD_CLIENT_ID": "1", "DISCORD_CLIENT_SECRET": "2", "DISCORD_TOKEN": "3", "BASE_URL": "http://localhost"},
    ):
        req = MagicMock()
        sess = {}
        with patch("app.ui.auth.add_toast"):
            with patch("app.ui.helpers.is_dashboard_admin", return_value=True):
                # Trigger endpoint
                res = await discord_callback(req, sess, "auth_code")

                # Should redirect appropriately setting auth context along the way
                assert res.status_code == 303
                assert sess["auth"]["id"] == "123"


# ── auth_before edge cases ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_auth_before_admin_revoked():
    """An admin route with revoked privileges should redirect to /profile."""
    sess = {"auth": {"id": "789", "user": "formerly_admin"}}
    req = MagicMock()
    req.scope = {}
    req.url.path = "/admin/some-page"

    with patch("app.ui.helpers.is_dashboard_admin", return_value=False):
        with patch("app.ui.auth.add_toast"):
            redirect = await auth_before(req, sess)
            assert redirect.status_code == 303
            # Should redirect to profile, not login
            assert "/profile" in str(redirect.headers.get("location", redirect.body))


@pytest.mark.asyncio
async def test_auth_before_dashboard_missing_token():
    """A dashboard route with no access_token in session should redirect to login."""
    sess = {"auth": {"id": "123", "token_data": {}}}
    req = MagicMock()
    req.scope = {}
    req.url.path = "/dashboard/456/settings"

    with patch("app.ui.auth.add_toast"):
        redirect = await auth_before(req, sess)
        assert redirect.status_code == 303


@pytest.mark.asyncio
async def test_auth_before_dashboard_valid_access():
    """A dashboard route with valid guild access should pass through."""
    sess = {"auth": {"id": "123", "token_data": {"access_token": "valid_token"}}}
    req = MagicMock()
    req.scope = {}
    req.url.path = "/dashboard/456/settings"

    with patch("app.ui.helpers.get_admin_guilds", new_callable=AsyncMock) as mock_guilds:
        mock_guilds.return_value = {"456": {"id": "456", "name": "Test Server"}}
        result = await auth_before(req, sess)
        # Should return None (pass through, no redirect)
        assert result is None


@pytest.mark.asyncio
async def test_auth_before_dashboard_unauthorized_guild():
    """A dashboard route for a guild the user doesn't have access to should redirect."""
    sess = {"auth": {"id": "123", "token_data": {"access_token": "valid_token"}}}
    req = MagicMock()
    req.scope = {}
    req.url.path = "/dashboard/999/settings"

    with patch("app.ui.helpers.get_admin_guilds", new_callable=AsyncMock) as mock_guilds:
        mock_guilds.return_value = {"456": {"id": "456", "name": "Other Server"}}
        with patch("app.ui.auth.add_toast"):
            redirect = await auth_before(req, sess)
            assert redirect.status_code == 303


@pytest.mark.asyncio
async def test_auth_before_dashboard_validation_error():
    """A dashboard route where guild validation throws should redirect safely."""
    sess = {"auth": {"id": "123", "token_data": {"access_token": "valid_token"}}}
    req = MagicMock()
    req.scope = {}
    req.url.path = "/dashboard/456/settings"

    with patch("app.ui.helpers.get_admin_guilds", new_callable=AsyncMock) as mock_guilds:
        mock_guilds.side_effect = Exception("API timeout")
        with patch("app.ui.auth.add_toast"):
            redirect = await auth_before(req, sess)
            assert redirect.status_code == 303


# ── dev_login tests ──────────────────────────────────────────────────


def test_dev_login_in_debug_mode():
    """dev_login should create a synthetic admin session when DEBUG is set."""
    from app.ui.auth import dev_login

    sess = {}
    with patch.dict(os.environ, {"DEBUG": "1", "BASE_URL": "http://localhost:5001"}):
        res = dev_login(sess)
        assert res.status_code == 303
        assert sess["auth"]["username"] == "DevAdmin"
        assert sess["auth"]["is_dashboard_admin"] is True


def test_dev_login_blocked_in_production():
    """dev_login should redirect to login when not in debug/local mode."""
    from app.ui.auth import dev_login

    sess = {}
    with patch.dict(os.environ, {"BASE_URL": "https://production.example.com"}, clear=False):
        # Ensure DEBUG is not set
        env = os.environ.copy()
        env.pop("DEBUG", None)
        with patch.dict(os.environ, env, clear=True):
            res = dev_login(sess)
            assert res.status_code == 303
            assert "auth" not in sess
