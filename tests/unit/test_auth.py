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
    with patch.dict(
        os.environ,
        {"POWERCORD_DISCORD_CLIENT_ID": "1", "POWERCORD_DISCORD_CLIENT_SECRET": "2", "POWERCORD_DISCORD_TOKEN": "3"},
    ):
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
    req.headers = {"host": "localhost"}
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
@patch("app.ui.helpers.get_admin_guilds", new_callable=AsyncMock)
@patch("httpx.AsyncClient")
async def test_discord_callback_success(mock_client, mock_get_admin_guilds):
    """Integrates successful logic parsing: exchange for tokens via mocked httpx -> user info fetch -> user validation."""
    # get_admin_guilds returns non-empty dict when user has access
    mock_get_admin_guilds.return_value = {"1": {"id": "1", "name": "Test Guild", "permissions": "8"}}

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
        {
            "POWERCORD_DISCORD_CLIENT_ID": "1",
            "POWERCORD_DISCORD_CLIENT_SECRET": "2",
            "POWERCORD_DISCORD_TOKEN": "3",
        },
    ):
        req = MagicMock()
        req.headers = {"host": "localhost"}
        sess = {}
        with patch("app.ui.auth.add_toast"):
            with patch("app.ui.helpers.is_dashboard_admin", return_value=True):
                # Trigger endpoint
                res = await discord_callback(req, sess, "auth_code")

                # Should redirect appropriately setting auth context along the way
                assert res.status_code == 303
                assert res.headers["location"] == "/profile"
                assert sess["auth"]["id"] == "123"


@pytest.mark.asyncio
@patch("app.ui.helpers.get_admin_guilds", new_callable=AsyncMock)
@patch("httpx.AsyncClient")
async def test_discord_callback_role_based_access(mock_client, mock_get_admin_guilds):
    """A user with a DashboardAccessRole (but NOT Discord Admin) should be able to log in."""
    # get_admin_guilds returns access via DashboardAccessRole, not Discord Admin perm
    mock_get_admin_guilds.return_value = {"1": {"id": "1", "name": "Role Access Guild", "permissions": "0"}}

    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {"access_token": "acc_tok"}

    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.json.return_value = {"id": "456", "username": "roleuser"}

    mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp1)
    mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp2)

    with patch.dict(
        os.environ,
        {
            "POWERCORD_DISCORD_CLIENT_ID": "1",
            "POWERCORD_DISCORD_CLIENT_SECRET": "2",
            "POWERCORD_DISCORD_TOKEN": "3",
        },
    ):
        req = MagicMock()
        req.headers = {"host": "localhost"}
        sess = {}
        with patch("app.ui.auth.add_toast"):
            with patch("app.ui.helpers.is_dashboard_admin", return_value=False):
                res = await discord_callback(req, sess, "auth_code")

                # Should still succeed — role-based access is sufficient
                assert res.status_code == 303
                assert res.headers["location"] == "/profile"
                assert sess["auth"]["id"] == "456"
                assert sess["auth"]["is_dashboard_admin"] is False


@pytest.mark.asyncio
@patch("app.ui.helpers.get_admin_guilds", new_callable=AsyncMock)
@patch("httpx.AsyncClient")
async def test_discord_callback_no_access_at_all(mock_client, mock_get_admin_guilds):
    """A user with no dashboard access (no Discord Admin, no roles) should be rejected."""
    # get_admin_guilds returns empty dict — no access
    mock_get_admin_guilds.return_value = {}

    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {"access_token": "acc_tok"}

    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.json.return_value = {"id": "789", "username": "nobody"}

    mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp1)
    mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp2)

    with patch.dict(
        os.environ,
        {
            "POWERCORD_DISCORD_CLIENT_ID": "1",
            "POWERCORD_DISCORD_CLIENT_SECRET": "2",
            "POWERCORD_DISCORD_TOKEN": "3",
        },
    ):
        req = MagicMock()
        req.headers = {"host": "localhost"}
        sess = {}
        with patch("app.ui.auth.add_toast"):
            res = await discord_callback(req, sess, "auth_code")

            # Should be rejected — redirect back to /login
            assert res.status_code == 303
            assert res.headers["location"] == "/login"
            assert "auth" not in sess


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
    req = MagicMock()
    req.url.hostname = "localhost"
    with patch.dict(os.environ, {"POWERCORD_DEBUG": "1"}):
        res = dev_login(req, sess)
        assert res.status_code == 303
        assert res.headers["location"] == "/profile"
        assert sess["auth"]["username"] == "DevAdmin"
        assert sess["auth"]["is_dashboard_admin"] is True


def test_dev_login_blocked_in_production():
    """dev_login should redirect to login when not in debug/local mode."""
    from app.ui.auth import dev_login

    sess = {}
    req = MagicMock()
    req.url.hostname = "production.example.com"
    # Ensure DEBUG is not set
    env = os.environ.copy()
    env.pop("POWERCORD_DEBUG", None)
    with patch.dict(os.environ, env, clear=True):
        res = dev_login(req, sess)
        assert res.status_code == 303
        assert "auth" not in sess


# ── get_redirect_uri tests ──────────────────────────────────────────


def test_get_redirect_uri_whitelisted_hosts():
    from app.ui.auth import get_redirect_uri

    # Test cases: (host, expected_redirect_uri, optional_headers, optional_scheme)
    cases = [
        # localhost
        ("localhost", "http://localhost/auth/discord/callback", None, "http"),
        ("localhost:5001", "http://localhost:5001/auth/discord/callback", None, "http"),
        ("sub.localhost:3000", "http://sub.localhost:3000/auth/discord/callback", None, "http"),
        # 127.0.0.1
        ("127.0.0.1", "http://127.0.0.1/auth/discord/callback", None, "http"),
        ("127.0.0.1:8000", "http://127.0.0.1:8000/auth/discord/callback", None, "http"),
        # midi.gallery
        ("midi.gallery", "http://midi.gallery/auth/discord/callback", None, "http"),
        ("sub.midi.gallery", "http://sub.midi.gallery/auth/discord/callback", None, "http"),
        ("foo.bar.midi.gallery:443", "http://foo.bar.midi.gallery:443/auth/discord/callback", None, "http"),
        # powercord.rocks
        ("powercord.rocks", "http://powercord.rocks/auth/discord/callback", None, "http"),
        ("dev.powercord.rocks:8080", "http://dev.powercord.rocks:8080/auth/discord/callback", None, "http"),
        # HTTPS via x-forwarded-proto
        ("powercord.rocks", "https://powercord.rocks/auth/discord/callback", {"x-forwarded-proto": "https"}, "http"),
        ("midi.gallery", "https://midi.gallery/auth/discord/callback", {"x-forwarded-proto": "https"}, "http"),
        # host header
        ("powercord.rocks", "http://powercord.rocks/auth/discord/callback", {"host": "powercord.rocks"}, "http"),
        # x-forwarded-host header
        ("midi.gallery", "http://midi.gallery/auth/discord/callback", {"x-forwarded-host": "midi.gallery"}, "http"),
    ]

    for host, expected, headers_dict, url_scheme in cases:
        req = MagicMock()

        # Setup headers
        if headers_dict:
            req.headers = {"host": host, **headers_dict}
        else:
            req.headers = {"host": host}

        # Setup URL
        req.url = MagicMock()
        req.url.scheme = url_scheme
        # Netloc/hostname mock returns
        if ":" in host:
            req.url.netloc = host
            req.url.hostname = host.split(":")[0]
        else:
            req.url.netloc = host
            req.url.hostname = host

        with patch.dict(
            os.environ, {"POWERCORD_ALLOWED_DOMAINS": "midi.gallery,powercord.rocks,localhost,127.0.0.1"}, clear=True
        ):
            res = get_redirect_uri(req)
            assert res == expected, f"Expected {expected} for host={host}, headers={headers_dict}, got {res}"


def test_get_redirect_uri_untrusted_host():
    from starlette.exceptions import HTTPException

    from app.ui.auth import get_redirect_uri

    req = MagicMock()
    req.headers = {"host": "attacker.com"}
    req.url = MagicMock()
    req.url.netloc = "attacker.com"
    req.url.hostname = "attacker.com"

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(HTTPException) as exc_info:
            get_redirect_uri(req)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Untrusted Host"


def test_get_redirect_uri_raw_mock_robustness():
    from starlette.exceptions import HTTPException

    from app.ui.auth import get_redirect_uri

    req = MagicMock()
    # A completely raw MagicMock will have all attributes return other MagicMocks.
    # It should raise HTTPException since it is not in the whitelist.
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(HTTPException) as exc_info:
            get_redirect_uri(req)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Untrusted Host"
