from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.dependencies import api_scope_required, get_current_api_user
from app.db.models import AdminUser, ApiAccessRole, ApiKey, DashboardAccessRole, GuildExtensionSettings


@pytest.fixture
def mock_get_internal_key():
    with patch("app.api.dependencies.get_or_create_internal_key", return_value="test_internal_key") as mock:
        yield mock


@pytest.fixture
def mock_session():
    with (
        patch("app.api.dependencies.Session") as mock_session_cls,
        patch("app.api.dependencies.init_connection_engine"),
    ):
        session_mock = MagicMock()
        mock_session_cls.return_value = session_mock
        session_mock.__enter__.return_value = session_mock
        yield session_mock


@pytest.mark.asyncio
async def test_get_current_api_user_internal_key(mock_get_internal_key):
    request = MagicMock()

    result = await get_current_api_user(request=request, token="test_internal_key")

    assert result["identity"] == "system_internal"
    assert "global.admin" in result["scopes"]
    assert request.state.user_identity == "system_internal"


@pytest.mark.asyncio
async def test_get_current_api_user_db_api_key(mock_session, mock_get_internal_key):
    request = MagicMock()

    import hashlib

    db_token_hash = hashlib.sha256(b"db_token").hexdigest()
    mock_api_key = ApiKey(name="test_key", key_hash=db_token_hash, scopes='["test_scope"]')
    mock_session.exec.return_value.first.return_value = mock_api_key

    result = await get_current_api_user(request=request, token="db_token")

    assert result["identity"] == "api_key_test_key"
    assert "test_scope" in result["scopes"]


@pytest.mark.asyncio
@patch("app.api.dependencies.httpx.AsyncClient")
async def test_get_current_api_user_discord_admin(mock_async_client, mock_session, mock_get_internal_key):
    request = MagicMock()

    # Mock Discord API Response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "123456789"}

    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_resp
    mock_async_client.return_value = mock_client_instance
    mock_client_instance.__aenter__.return_value = mock_client_instance

    # Mock Admin Check (Returns an AdminUser)
    mock_session.exec.return_value.first.side_effect = [None, AdminUser(user_id=123456789)]

    result = await get_current_api_user(request=request, token="discord_oauth_token")

    assert result["identity"] == "discord_user_123456789"
    assert "global.admin" in result["scopes"]


@pytest.mark.asyncio
@patch("app.api.dependencies.httpx.AsyncClient")
async def test_get_current_api_user_discord_rbac(mock_async_client, mock_session, mock_get_internal_key):
    request = MagicMock()

    # Needs to bypass ApiKey check, bypass AdminUser check
    mock_session.exec.return_value.first.side_effect = [None, None]

    # Mock discord /@me, then /@me/guilds, then Mock Admin API /roles
    mock_me_resp = MagicMock()
    mock_me_resp.status_code = 200
    mock_me_resp.json.return_value = {"id": "999"}

    mock_guilds_resp = MagicMock()
    mock_guilds_resp.status_code = 200
    mock_guilds_resp.json.return_value = [{"id": "123", "permissions": "0"}]

    mock_roles_resp = MagicMock()
    mock_roles_resp.status_code = 200
    mock_roles_resp.json.return_value = {"roles": ["111", "222"]}

    mock_client_instance = AsyncMock()
    mock_client_instance.get.side_effect = [mock_me_resp, mock_guilds_resp, mock_roles_resp]
    mock_async_client.return_value = mock_client_instance
    mock_client_instance.__aenter__.return_value = mock_client_instance

    # Mock DashboardAccessRole results (none) and ApiAccessRole results
    mock_access_role = ApiAccessRole(guild_id=123, role_id=222, extension_name="test_extension")

    # We query DashboardAccessRole then ApiAccessRole in the session
    mock_session.exec.return_value.all.side_effect = [[], [mock_access_role]]

    result = await get_current_api_user(request=request, token="discord_oauth_token", x_guild_id=123)

    assert result["identity"] == "discord_user_999"
    assert "123.test_extension.admin" in result["scopes"]
    assert "123.test_extension.user" in result["scopes"]


@pytest.mark.asyncio
@patch("app.api.dependencies.httpx.AsyncClient")
async def test_get_current_api_user_discord_admin_guild(mock_async_client, mock_session, mock_get_internal_key):
    request = MagicMock()

    # Needs to bypass ApiKey check, bypass AdminUser check
    mock_session.exec.return_value.first.side_effect = [None, None]

    # Mock discord /@me, then /@me/guilds (with ADMIN_PERM = 8), then Mock Admin API /roles
    mock_me_resp = MagicMock()
    mock_me_resp.status_code = 200
    mock_me_resp.json.return_value = {"id": "999"}

    mock_guilds_resp = MagicMock()
    mock_guilds_resp.status_code = 200
    # 8 is 1 << 3 (ADMINISTRATOR)
    mock_guilds_resp.json.value = [{"id": "123", "permissions": "8"}]
    mock_guilds_resp.json.return_value = [{"id": "123", "permissions": "8"}]

    mock_roles_resp = MagicMock()
    mock_roles_resp.status_code = 200
    mock_roles_resp.json.return_value = {"roles": []}

    mock_client_instance = AsyncMock()
    mock_client_instance.get.side_effect = [mock_me_resp, mock_guilds_resp, mock_roles_resp]
    mock_async_client.return_value = mock_client_instance
    mock_client_instance.__aenter__.return_value = mock_client_instance

    # Mock GuildExtensionSettings query for the admin permission check
    mock_cog = GuildExtensionSettings(guild_id=123, extension_name="test_extension", gadget_type="cog", is_enabled=True)
    # mock_session.exec for get_current_api_user will call GuildExtensionSettings, then DashboardAccessRole, then ApiAccessRole
    # We returned mock_cog, then for DashboardAccessRole/ApiAccessRole we return empty lists.
    mock_session.exec.return_value.all.side_effect = [[mock_cog], [], []]

    result = await get_current_api_user(request=request, token="discord_oauth_token", x_guild_id=123)

    assert result["identity"] == "discord_user_999"
    assert "123.test_extension.admin" in result["scopes"]
    assert "123.test_extension.user" in result["scopes"]


@pytest.mark.asyncio
@patch("app.api.dependencies.httpx.AsyncClient")
async def test_get_current_api_user_discord_dashboard_role(mock_async_client, mock_session, mock_get_internal_key):
    request = MagicMock()

    # Needs to bypass ApiKey check, bypass AdminUser check
    mock_session.exec.return_value.first.side_effect = [None, None]

    # Mock discord /@me, then /@me/guilds, then Mock Admin API /roles
    mock_me_resp = MagicMock()
    mock_me_resp.status_code = 200
    mock_me_resp.json.return_value = {"id": "999"}

    mock_guilds_resp = MagicMock()
    mock_guilds_resp.status_code = 200
    mock_guilds_resp.json.return_value = [{"id": "123", "permissions": "0"}]

    mock_roles_resp = MagicMock()
    mock_roles_resp.status_code = 200
    mock_roles_resp.json.return_value = {"roles": ["111"]}

    mock_client_instance = AsyncMock()
    mock_client_instance.get.side_effect = [mock_me_resp, mock_guilds_resp, mock_roles_resp]
    mock_async_client.return_value = mock_client_instance
    mock_client_instance.__aenter__.return_value = mock_client_instance

    # Query DashboardAccessRole (returns match) and ApiAccessRole (returns none)
    mock_dr = DashboardAccessRole(guild_id=123, role_id=111)
    mock_cog = GuildExtensionSettings(guild_id=123, extension_name="test_extension", gadget_type="cog", is_enabled=True)
    mock_session.exec.return_value.all.side_effect = [[mock_dr], [], [mock_cog]]

    result = await get_current_api_user(request=request, token="discord_oauth_token", x_guild_id=123)

    assert result["identity"] == "discord_user_999"
    assert "123.test_extension.user" in result["scopes"]
    assert "123.test_extension.admin" not in result["scopes"]


@pytest.mark.asyncio
async def test_api_scope_required_global_override():
    request = MagicMock()
    user_dict = {"identity": "system_internal", "scopes": ["global.admin"]}

    checker = api_scope_required("some_restricted_scope")
    result = await checker(request=request, user=user_dict)

    # Because they have global.admin, they should pass regardless of the required scope.
    assert result == user_dict


@pytest.mark.asyncio
async def test_api_scope_required_core_admin_override():
    request = MagicMock()
    user_dict = {"identity": "some_user", "scopes": ["core.admin"]}

    checker = api_scope_required("some_restricted_scope")
    result = await checker(request=request, user=user_dict)

    assert result == user_dict


@pytest.mark.asyncio
async def test_api_scope_required_extension_wide_scope():
    request = MagicMock()
    user_dict = {"identity": "some_user", "scopes": ["global.honeypot.user"]}

    # Match user level scope
    checker = api_scope_required("honeypot", level="user")
    result = await checker(request=request, user=user_dict)
    assert result == user_dict

    # Fails admin level scope
    checker_admin = api_scope_required("honeypot", level="admin")
    with pytest.raises(HTTPException) as excinfo:
        await checker_admin(request=request, user=user_dict)
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_api_scope_required_guild_scopes():
    # Test path parameter resolution
    request_path = MagicMock()
    request_path.path_params = {"guild_id": "777"}
    request_path.query_params = {}
    request_path.headers = {}

    user_dict = {"identity": "some_user", "scopes": ["777.honeypot.admin"]}

    checker = api_scope_required("honeypot", level="admin")
    result = await checker(request=request_path, user=user_dict)
    assert result == user_dict

    # Test query param resolution
    request_query = MagicMock()
    request_query.path_params = {}
    request_query.query_params = {"x_guild_id": "777"}
    request_query.headers = {}
    result = await checker(request=request_query, user=user_dict)
    assert result == user_dict

    # Test header resolution
    request_header = MagicMock()
    request_header.path_params = {}
    request_header.query_params = {}
    request_header.headers = {"x-guild-id": "777"}
    result = await checker(request=request_header, user=user_dict)
    assert result == user_dict


@pytest.mark.asyncio
async def test_api_scope_required_fallback_and_failure():
    request = MagicMock()
    request.path_params = {}
    request.query_params = {}
    request.headers = {}

    # Direct fallback match
    user_dict = {"identity": "some_user", "scopes": ["honeypot"]}
    checker = api_scope_required("honeypot", level="user")
    result = await checker(request=request, user=user_dict)
    assert result == user_dict

    # Failure
    user_dict_fail = {"identity": "some_user", "scopes": ["wrong_scope"]}
    with pytest.raises(HTTPException) as excinfo:
        await checker(request=request, user=user_dict_fail)

    assert excinfo.value.status_code == 403
    assert "Missing required scope" in excinfo.value.detail
