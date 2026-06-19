from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import DiscordChannel, DiscordRole, GuildExtensionSettings
from app.extensions.utilities.widget import SecurityRuleEngine, get_effective_channel_permissions
from app.ui.dashboard import dashboard_ping_bot, dashboard_scan_guild

pytestmark = pytest.mark.unit


def test_security_rule_engine_empty_db(session):
    """Verify that SecurityRuleEngine handles completely empty databases gracefully."""
    guild_id = 999888

    # Evaluate on clean/empty session
    result = SecurityRuleEngine.evaluate(guild_id, session)

    # Empty DB has honeypot disabled, resulting in a low severity alert
    assert result["score"] == 95
    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["rule"] == "Suggestive Honeypot Integration"


def test_security_rule_engine_with_honeypot_enabled(session):
    """Verify that SecurityRuleEngine returns a perfect score of 100 when honeypot is enabled and no issues exist."""
    guild_id = 54321

    # Enable honeypot globally and locally
    global_ext = GuildExtensionSettings(guild_id=0, extension_name="honeypot", gadget_type="widget", is_enabled=True)
    local_ext = GuildExtensionSettings(
        guild_id=guild_id, extension_name="honeypot", gadget_type="widget", is_enabled=True
    )
    session.add(global_ext)
    session.add(local_ext)
    session.commit()

    try:
        result = SecurityRuleEngine.evaluate(guild_id, session)
        assert result["score"] == 100
        assert result["alerts"] == []
    finally:
        session.delete(global_ext)
        session.delete(local_ext)
        session.commit()


def test_security_rule_engine_score_lower_boundary():
    """Verify that the security score is clamped at 0 and doesn't become negative."""
    engine = SecurityRuleEngine()

    # Let's mock evaluate to return a high number of high severity alerts
    dummy_high_alerts = [
        {"rule": "Dummy Rule", "category": "exposure", "severity": "high", "message": "leak"},
    ] * 10  # 10 * 15 = 150 points reduction

    for rule in engine.rules:
        # Patch evaluate to return 5 high alerts each
        rule.evaluate = MagicMock(return_value=dummy_high_alerts)

    result = engine.run_all(12345, MagicMock())

    assert result["score"] == 0
    assert len(result["alerts"]) == 80  # 8 rules * 10 alerts


def test_security_rule_engine_score_decrements():
    """Verify exact decrements for alert severities: high (15), medium (10), low (5)."""
    engine = SecurityRuleEngine()

    # We will stub the evaluate methods to return 1 high, 1 medium, 1 low alert total
    engine.rules[0].evaluate = MagicMock(return_value=[{"severity": "high"}])
    engine.rules[1].evaluate = MagicMock(return_value=[{"severity": "medium"}])
    engine.rules[2].evaluate = MagicMock(return_value=[{"severity": "low"}])
    # The rest return empty
    for i in range(3, len(engine.rules)):
        engine.rules[i].evaluate = MagicMock(return_value=[])

    result = engine.run_all(12345, MagicMock())
    # 100 - 15 - 10 - 5 = 70
    assert result["score"] == 70


def test_security_rule_engine_invalid_overwrites_json(session):
    """Verify that malformed overwrites JSON does not crash rule evaluation."""
    guild_id = 99999

    # Enable honeypot
    ext = GuildExtensionSettings(guild_id=guild_id, extension_name="honeypot", gadget_type="widget", is_enabled=True)
    session.add(ext)

    # Insert role
    everyone_role = DiscordRole(
        id=guild_id,
        guild_id=guild_id,
        name="@everyone",
        permissions=0,
        position=0,
    )
    session.add(everyone_role)

    # Insert channel with malformed JSON overwrites
    channel = DiscordChannel(
        id=101, guild_id=guild_id, name="rules", type="text", position=1, overwrites="{invalid_json_here"
    )
    session.add(channel)
    session.commit()

    try:
        # Call evaluate
        result = SecurityRuleEngine.evaluate(guild_id, session)

        # Should not crash, and score should still be 100 since the invalid json channel
        # was skipped gracefully inside the rules and honeypot is enabled.
        assert result["score"] == 100
    finally:
        session.delete(ext)
        session.delete(everyone_role)
        session.delete(channel)
        session.commit()


def test_get_effective_channel_permissions_none_everyone():
    """Verify get_effective_channel_permissions behavior when everyone_role is None."""
    role = DiscordRole(id=111, guild_id=999, name="Test", permissions=1024, position=1)
    channel = DiscordChannel(id=222, guild_id=999, name="chan", type="text", position=1)

    overwrites = {"111": {"allow": 2048, "deny": 0}}

    # Should not crash and should resolve permissions based on role.guild_id as fallback key
    perms = get_effective_channel_permissions(role, channel, None, overwrites)
    assert perms & 2048


@patch("app.ui.dashboard.get_internal_api_client")
@pytest.mark.asyncio
async def test_dashboard_scan_guild_bot_port_error(mock_client_cls, monkeypatch):
    """Verify that a non-integer POWERCORD_BOT_API_PORT environment variable causes ValueError."""
    monkeypatch.setenv("POWERCORD_BOT_API_PORT", "not_an_integer")

    with pytest.raises(ValueError):
        await dashboard_scan_guild(999)


@patch("app.ui.dashboard.get_internal_api_client")
@pytest.mark.asyncio
async def test_dashboard_ping_bot_port_error(mock_client_cls, monkeypatch):
    """Verify that a non-integer POWERCORD_BOT_API_PORT environment variable causes ValueError."""
    monkeypatch.setenv("POWERCORD_BOT_API_PORT", "not_an_integer")

    with pytest.raises(ValueError):
        await dashboard_ping_bot(999)


@patch("app.ui.dashboard.get_internal_api_client")
@pytest.mark.asyncio
async def test_dashboard_ping_bot_malformed_json_response(mock_client_cls):
    """Verify that the ping bot route handles malformed json responses from the bot gracefully."""
    mock_client = AsyncMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_client

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # Returns JSON without 'bot' key
    mock_resp.json.return_value = {"something": "else"}
    mock_client.get.return_value = mock_resp

    res = await dashboard_ping_bot(999)
    rendered_str = res.__html__()

    assert "Disconnected" in rendered_str
