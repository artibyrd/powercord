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
