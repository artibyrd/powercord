import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.api.dependencies import get_current_api_user  # noqa: E402
from app.bot.internal_server import api, set_bot_instance, start_bot_api  # noqa: E402


def override_get_current_api_user():
    return {"identity": "system_internal", "scopes": ["global"]}


api.dependency_overrides[get_current_api_user] = override_get_current_api_user

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit

client = TestClient(api)


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.guilds = [MagicMock(member_count=10), MagicMock(member_count=20)]
    bot.latency = 0.05
    bot.extensions = ["app.extensions.example_extension.cog"]

    # Mock async method
    bot.rollout_application_commands = AsyncMock()

    set_bot_instance(bot)
    return bot


@patch("psutil.cpu_percent")
@patch("psutil.virtual_memory")
def test_get_stats(mock_memory, mock_cpu, mock_bot):
    mock_cpu.return_value = 15.5
    mock_memory.return_value = MagicMock(percent=40.0, used=4 * 1024**3, total=10 * 1024**3)

    response = client.get("/stats")

    assert response.status_code == 200
    data = response.json()

    assert data["system"]["cpu_percent"] == 15.5
    assert data["system"]["memory_percent"] == 40.0
    assert data["bot"]["guilds"] == 2
    assert data["bot"]["users"] == 30
    assert data["bot"]["latency"] == 50


def test_get_stats_no_bot():
    set_bot_instance(None)
    response = client.get("/stats")
    assert response.status_code == 503


def test_reload_extension_success(mock_bot):
    response = client.post("/extensions/example_extension/reload")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_bot.reload_extension.assert_called_with("app.extensions.example_extension.cog")
    mock_bot.rollout_application_commands.assert_called_once()


def test_reload_extension_not_loaded(mock_bot):
    mock_bot.extensions = []

    response = client.post("/extensions/new_extension/reload")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_bot.load_extension.assert_called_with("app.extensions.new_extension.cog")
    mock_bot.rollout_application_commands.assert_called_once()


def test_reload_extension_error(mock_bot):
    mock_bot.reload_extension.side_effect = Exception("TestError")
    response = client.post("/extensions/example_extension/reload")
    assert response.status_code == 500


def test_reload_extension_no_bot():
    set_bot_instance(None)
    response = client.post("/extensions/example_extension/reload")
    assert response.status_code == 503


def test_get_logs_no_file(tmp_path):
    with patch("app.bot.internal_server.Path.resolve") as mock_resolve:
        mock_resolve.return_value.parents = [None, tmp_path]
        response = client.get("/logs")
        assert response.status_code == 200
        assert "Log file not found" in response.json()["logs"][0]


def test_get_logs_success(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "powercord.log"
    log_file.write_text("line1\nline2\n")

    with patch("app.bot.internal_server.Path.resolve") as mock_resolve:
        mock_resolve.return_value.parents = [None, tmp_path]
        response = client.get("/logs?limit=1")
        assert response.status_code == 200
        assert response.json()["logs"] == ["line2\n"]


def test_get_logs_error(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "powercord.log"
    log_file.write_text("line1\nline2\n")

    with (
        patch("app.bot.internal_server.Path.resolve") as mock_resolve,
        patch("app.bot.internal_server.open", side_effect=Exception("ReadError")),
    ):
        mock_resolve.return_value.parents = [None, tmp_path]
        response = client.get("/logs")
        assert response.status_code == 200
        assert "Error reading logs" in response.json()["logs"][0]


def test_reload_config_with_zero_guild_id(mock_bot):
    response = client.post("/config/reload", json={"guild_id": 0})

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "guild 0" in response.json()["message"]


def test_reload_config_no_guild_id(mock_bot):
    response = client.post("/config/reload", json={})
    assert response.status_code == 400


def test_reload_config_no_bot():
    set_bot_instance(None)
    response = client.post("/config/reload", json={"guild_id": 0})
    assert response.status_code == 503


def test_toggle_example_counters_start(mock_bot):
    mock_cog = MagicMock()
    mock_cog.start_counters = MagicMock()
    mock_bot.get_cog.return_value = mock_cog

    response = client.post("/examples/counters", json={"action": "start"})
    assert response.status_code == 200
    mock_cog.start_counters.assert_called_once()


def test_toggle_example_counters_stop(mock_bot):
    mock_cog = MagicMock()
    mock_cog.stop_counters = MagicMock()
    mock_bot.get_cog.return_value = mock_cog

    response = client.post("/examples/counters", json={"action": "stop"})
    assert response.status_code == 200
    mock_cog.stop_counters.assert_called_once()


def test_toggle_example_counters_invalid_action(mock_bot):
    response = client.post("/examples/counters", json={"action": "invalid"})
    assert response.status_code == 400


def test_toggle_example_counters_no_cog(mock_bot):
    mock_bot.get_cog.return_value = None
    response = client.post("/examples/counters", json={"action": "start"})
    assert response.status_code == 404


def test_toggle_example_counters_missing_method(mock_bot):
    mock_cog = object()  # Has no start_counters
    mock_bot.get_cog.return_value = mock_cog

    response = client.post("/examples/counters", json={"action": "start"})
    assert response.status_code == 500

    response = client.post("/examples/counters", json={"action": "stop"})
    assert response.status_code == 500


def test_toggle_example_counters_no_bot():
    set_bot_instance(None)
    response = client.post("/examples/counters", json={"action": "start"})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_start_bot_api():
    mock_bot = MagicMock()
    with patch("app.bot.internal_server.Server") as mock_server_cls, patch("app.bot.internal_server.Config"):
        mock_server = AsyncMock()
        mock_server_cls.return_value = mock_server

        await start_bot_api(mock_bot)
        mock_server.serve.assert_called_once()


@pytest.mark.asyncio
async def test_start_bot_api_error():
    mock_bot = MagicMock()
    with (
        patch("app.bot.internal_server.Server") as mock_server_cls,
        patch("app.bot.internal_server.Config"),
        patch("app.bot.internal_server.logging.error") as mock_log,
    ):
        mock_server = AsyncMock()
        mock_server.serve.side_effect = Exception("ServeError")
        mock_server_cls.return_value = mock_server

        await start_bot_api(mock_bot)
        mock_log.assert_called_once()


# ── unload_extension endpoint tests ──────────────────────────────────


def test_unload_extension_loaded(mock_bot):
    """Unloading a loaded extension should succeed and trigger command rollout."""
    mock_bot.extensions = ["app.extensions.test_ext.cog"]
    response = client.post("/extensions/test_ext/unload")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_bot.unload_extension.assert_called_with("app.extensions.test_ext.cog")
    mock_bot.rollout_application_commands.assert_called_once()


def test_unload_extension_not_loaded(mock_bot):
    """Unloading an extension that isn't loaded should succeed with 'not loaded' message."""
    mock_bot.extensions = []
    response = client.post("/extensions/test_ext/unload")
    assert response.status_code == 200
    assert "not loaded" in response.json()["message"]


def test_unload_extension_error(mock_bot):
    """Errors during unload should return 500."""
    mock_bot.extensions = ["app.extensions.test_ext.cog"]
    mock_bot.unload_extension.side_effect = Exception("UnloadFailed")
    response = client.post("/extensions/test_ext/unload")
    assert response.status_code == 500


def test_unload_extension_no_bot():
    """Unloading with no bot instance should return 503."""
    set_bot_instance(None)
    response = client.post("/extensions/test_ext/unload")
    assert response.status_code == 503


# ── hotload_check endpoint tests ─────────────────────────────────────


def test_hotload_check_safe(mock_bot):
    """A cog without preload requirements should report requires_restart=False."""
    mock_powerloader = MagicMock()
    mock_powerloader._hotload_caution.return_value = False
    mock_bot.get_cog.return_value = mock_powerloader

    response = client.get("/extensions/safe_cog/hotload-check")
    assert response.status_code == 200
    assert response.json()["requires_restart"] is False


def test_hotload_check_requires_restart(mock_bot):
    """A cog with preload requirements should report requires_restart=True."""
    mock_powerloader = MagicMock()
    mock_powerloader._hotload_caution.return_value = True
    mock_bot.get_cog.return_value = mock_powerloader

    response = client.get("/extensions/risky_cog/hotload-check")
    assert response.status_code == 200
    assert response.json()["requires_restart"] is True


def test_hotload_check_no_powerloader(mock_bot):
    """If AppPowerLoader isn't loaded, assume safe to hot-load."""
    mock_bot.get_cog.return_value = None
    response = client.get("/extensions/any_cog/hotload-check")
    assert response.status_code == 200
    assert response.json()["requires_restart"] is False


def test_hotload_check_no_bot():
    """Hotload check with no bot should return 503."""
    set_bot_instance(None)
    response = client.get("/extensions/any_cog/hotload-check")
    assert response.status_code == 503


# ── user guild roles endpoint tests ──────────────────────────────────


def test_get_user_guild_roles_success(mock_bot):
    """Should return role IDs for a valid user in a valid guild."""
    mock_guild = MagicMock()
    mock_member = MagicMock()
    mock_role1 = MagicMock()
    mock_role1.id = 111
    mock_role2 = MagicMock()
    mock_role2.id = 222
    mock_member.roles = [mock_role1, mock_role2]
    mock_guild.get_member.return_value = mock_member
    mock_bot.get_guild.return_value = mock_guild

    response = client.get("/user/123/guilds/456/roles")
    assert response.status_code == 200
    assert "111" in response.json()["roles"]
    assert "222" in response.json()["roles"]


def test_get_user_guild_roles_no_guild(mock_bot):
    """Non-existent guild should return 404."""
    mock_bot.get_guild.return_value = None
    response = client.get("/user/123/guilds/999/roles")
    assert response.status_code == 404


def test_get_user_guild_roles_no_member(mock_bot):
    """Non-existent member in a valid guild should return 404."""
    mock_guild = MagicMock()
    mock_guild.get_member.return_value = None
    mock_bot.get_guild.return_value = mock_guild
    response = client.get("/user/123/guilds/456/roles")
    assert response.status_code == 404


def test_get_user_guild_roles_no_bot():
    """User guild roles with no bot should return 503."""
    set_bot_instance(None)
    response = client.get("/user/123/guilds/456/roles")
    assert response.status_code == 503


# ── guild roles endpoint tests ───────────────────────────────────────


def test_get_guild_roles_success(mock_bot):
    """Should return roles (excluding @everyone) sorted by name."""
    mock_guild = MagicMock()
    role_admin = MagicMock()
    role_admin.id = 1
    role_admin.name = "Admin"
    role_admin.color = "0x00ff00"

    role_mod = MagicMock()
    role_mod.id = 2
    role_mod.name = "Moderator"
    role_mod.color = "0xff0000"

    role_everyone = MagicMock()
    role_everyone.name = "@everyone"

    mock_guild.roles = [role_everyone, role_mod, role_admin]
    mock_bot.get_guild.return_value = mock_guild

    response = client.get("/guilds/456/roles")
    assert response.status_code == 200
    roles = response.json()["roles"]
    assert len(roles) == 2
    # Should be sorted alphabetically (Admin before Moderator)
    assert roles[0]["name"] == "Admin"
    assert roles[1]["name"] == "Moderator"


def test_get_guild_roles_no_guild(mock_bot):
    """Non-existent guild should return 404."""
    mock_bot.get_guild.return_value = None
    response = client.get("/guilds/999/roles")
    assert response.status_code == 404


def test_get_guild_roles_no_bot():
    """Guild roles with no bot should return 503."""
    set_bot_instance(None)
    response = client.get("/guilds/456/roles")
    assert response.status_code == 503
