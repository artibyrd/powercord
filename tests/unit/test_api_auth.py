from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.dependencies import api_scope_required, get_current_api_user
from app.db.models import AdminUser, ApiAccessRole, ApiKey


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
    assert "global" in result["scopes"]
    assert request.state.user_identity == "system_internal"


@pytest.mark.asyncio
async def test_get_current_api_user_db_api_key(mock_session, mock_get_internal_key):
    request = MagicMock()

    mock_api_key = ApiKey(name="test_key", key="db_token", scopes='["test_scope"]')
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
    assert "global" in result["scopes"]


@pytest.mark.asyncio
@patch("app.api.dependencies.httpx.AsyncClient")
async def test_get_current_api_user_discord_rbac(mock_async_client, mock_session, mock_get_internal_key):
    request = MagicMock()

    # Needs to bypass ApiKey check, bypass AdminUser check
    mock_session.exec.return_value.first.side_effect = [None, None]

    # Mock discord /@me, then Mock Admin API /roles
    mock_me_resp = MagicMock()
    mock_me_resp.status_code = 200
    mock_me_resp.json.return_value = {"id": "999"}

    mock_roles_resp = MagicMock()
    mock_roles_resp.status_code = 200
    mock_roles_resp.json.return_value = {"roles": ["111", "222"]}

    mock_client_instance = AsyncMock()
    mock_client_instance.get.side_effect = [mock_me_resp, mock_roles_resp]
    mock_async_client.return_value = mock_client_instance
    mock_client_instance.__aenter__.return_value = mock_client_instance

    # Mock ApiAccessRole results
    mock_access_role = ApiAccessRole(guild_id=123, role_id=222, extension_name="test_extension")
    mock_session.exec.return_value.all.return_value = [mock_access_role]

    result = await get_current_api_user(request=request, token="discord_oauth_token", x_guild_id=123)

    assert result["identity"] == "discord_user_999"
    assert "test_extension" in result["scopes"]


@pytest.mark.asyncio
async def test_api_scope_required_global_override():
    user_dict = {"identity": "system_internal", "scopes": ["global"]}

    checker = api_scope_required("some_restricted_scope")
    result = await checker(user=user_dict)

    # Because they have global, they should pass regardless of the required scope.
    assert result == user_dict


@pytest.mark.asyncio
async def test_api_scope_required_missing_scope():
    user_dict = {"identity": "api_key_test", "scopes": ["wrong_scope"]}

    checker = api_scope_required("restricted_scope")
    with pytest.raises(HTTPException) as excinfo:
        await checker(user=user_dict)

    assert excinfo.value.status_code == 403
    assert "Missing required scope" in excinfo.value.detail
