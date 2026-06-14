import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import DiscordAuditorConfig
from app.ui.dashboard import get_alerts_list, post_auditor_settings

pytestmark = pytest.mark.unit


@patch("app.common.alchemy.init_connection_engine")
@patch("sqlmodel.Session")
@pytest.mark.asyncio
async def test_post_auditor_settings(mock_session_cls, mock_init_engine):
    guild_id = 999

    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session
    mock_session.exec.return_value.first.return_value = None  # New config

    req = MagicMock()
    req.form = AsyncMock(
        return_value={
            "staff_separator_role_id": "12345",
            "staff_channel_ids": "1001, 1002",
            "announcement_channel_ids": "2001",
        }
    )

    resp = await post_auditor_settings(guild_id, req)

    # Assertions
    assert resp.headers.get("HX-Refresh") == "true"
    mock_session.add.assert_called_once()
    args, _ = mock_session.add.call_args
    config = args[0]
    assert isinstance(config, DiscordAuditorConfig)
    assert config.guild_id == guild_id
    assert config.staff_separator_role_id == 12345
    assert json.loads(config.staff_channel_ids) == [1001, 1002]
    assert json.loads(config.announcement_channel_ids) == [2001]
    mock_session.commit.assert_called_once()


@patch("app.common.alchemy.init_connection_engine")
@patch("sqlmodel.Session")
@patch("app.extensions.utilities.widget.SecurityRuleEngine.evaluate")
@pytest.mark.asyncio
async def test_get_alerts_list(mock_evaluate, mock_session_cls, mock_init_engine):
    guild_id = 999

    # Mock SecurityRuleEngine.evaluate returning alerts
    mock_evaluate.return_value = {
        "score": 90,
        "alerts": [
            {"rule": "Rule A", "category": "exposure", "severity": "high", "message": "leak"},
            {"rule": "Rule B", "category": "roles", "severity": "low", "message": "role_ping"},
        ],
    }

    req = MagicMock()
    req.query_params = {"category": "exposure"}

    # We want to filter by category="exposure"
    res = await get_alerts_list(guild_id, req)

    # Verify evaluation was called
    mock_evaluate.assert_called_once()

    # Verify that only the "exposure" category alert was rendered.
    # The returned element should contain "Rule A" and not "Rule B"
    rendered_str = str(res)
    assert "Rule A" in rendered_str
    assert "Rule B" not in rendered_str
