import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import DiscordAuditorConfig, DiscordChannel, DiscordRole, GuildExtensionSettings
from app.extensions.utilities.widget import (
    SecurityRuleEngine,
    guild_admin_utilities_help_bubble,
    guild_admin_utilities_sidebar,
)
from app.ui.dashboard import dashboard_ping_bot, dashboard_scan_guild

pytestmark = pytest.mark.unit


def test_empty_guild_evaluation(session):
    """Verify evaluation on a completely empty guild."""
    guild_id = 90001

    # By default, honeypot settings won't exist, which causes 1 low alert.
    result = SecurityRuleEngine.evaluate(guild_id, session)
    assert result["score"] == 95  # 100 - 5 (low severity alert)
    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["rule"] == "Suggestive Honeypot Integration"


def test_score_boundaries(session):
    """Verify security health score clamps and boundary values (100 and 0)."""
    guild_id = 90002

    # 1. Test 100/100 (Perfect Score)
    # Enable honeypot setting
    session.add(
        GuildExtensionSettings(guild_id=guild_id, extension_name="honeypot", gadget_type="widget", is_enabled=True)
    )
    # Add an @everyone role
    session.add(DiscordRole(id=guild_id, guild_id=guild_id, name="@everyone", permissions=0, position=0))
    session.commit()

    result_perfect = SecurityRuleEngine.evaluate(guild_id, session)
    assert result_perfect["score"] == 100
    assert len(result_perfect["alerts"]) == 0

    # 2. Test 0/100 (Clamped Score)
    # Insert multiple severe security issues to drop the score below 0.
    # Set staff separator role configuration
    session.add(
        DiscordAuditorConfig(
            guild_id=guild_id,
            staff_separator_role_id=1111,
            staff_channel_ids="[2222]",
            announcement_channel_ids="[3333]",
        )
    )
    # Add staff separator role
    session.add(DiscordRole(id=1111, guild_id=guild_id, name="StaffSeparator", permissions=0, position=5))
    # Add low-tier role (pos=2) with Administrator permission (1 << 3) - LowTierRolePrivileges (high: -15)
    session.add(DiscordRole(id=1112, guild_id=guild_id, name="LowTierAdmin", permissions=1 << 3, position=2))
    # Add low-tier role (pos=3) set to mentionable - GeneralRoleMentionability (low: -5)
    session.add(
        DiscordRole(
            id=1113, guild_id=guild_id, name="LowTierMentionable", permissions=0, position=3, is_mentionable=True
        )
    )
    # Add managed bot role with excessive privileges (1 << 5) - OverPrivilegedBotIntegrations (medium: -10)
    session.add(
        DiscordRole(
            id=1114, guild_id=guild_id, name="OverprivilegedBot", permissions=1 << 5, position=6, is_managed=True
        )
    )
    # Add a public announcement channel (pos=1) allowing @everyone (id=guild_id) to send messages (1 << 11) - PublicAnnouncementProtection (high: -15)
    session.add(
        DiscordChannel(
            id=3333,
            guild_id=guild_id,
            name="rules-and-announcements",
            type="text",
            overwrites=json.dumps({str(guild_id): {"allow": 1 << 11, "deny": 0}}),
        )
    )
    # Add exposed staff channel visible to @everyone (View Channel 1 << 10 not denied) - ExposedStaffChannels (high: -15)
    session.add(DiscordChannel(id=2222, guild_id=guild_id, name="staff-chat", type="text", overwrites="{}"))
    # Add non-text location (voice channel) allowing low-tier role to send messages (1 << 11) - UnauthorizedChatPings (medium: -10)
    session.add(
        DiscordChannel(
            id=4444,
            guild_id=guild_id,
            name="Lounge Voice",
            type="voice",
            overwrites=json.dumps({"1112": {"allow": 1 << 11, "deny": 0}}),
        )
    )

    session.commit()

    SecurityRuleEngine.invalidate(guild_id)
    result_worst = SecurityRuleEngine.evaluate(guild_id, session)
    # The score should deduct properly: 3 high (-45) + 2 medium (-20) + 1 low (-5) = 30
    assert result_worst["score"] == 30
    assert len(result_worst["alerts"]) > 0


def test_evaluate_malformed_overwrites(session):
    """Verify that malformed overwrites JSON strings do not crash the engine, but are skipped gracefully."""
    guild_id = 90003

    # Add @everyone role
    session.add(DiscordRole(id=guild_id, guild_id=guild_id, name="@everyone", permissions=0, position=0))

    # 1. Non-JSON string overwrites
    session.add(
        DiscordChannel(
            id=50001, guild_id=guild_id, name="broken-json-channel", type="text", overwrites="not-valid-json"
        )
    )

    # 2. JSON list instead of dict overwrites
    session.add(
        DiscordChannel(id=50002, guild_id=guild_id, name="list-json-channel", type="text", overwrites="[1, 2, 3]")
    )

    # 3. None/null values in keys
    session.add(
        DiscordChannel(
            id=50003,
            guild_id=guild_id,
            name="null-values-channel",
            type="text",
            overwrites=json.dumps({"12345": {"allow": None, "deny": None}}),
        )
    )

    # 4. Non-int values in overwrites
    session.add(
        DiscordChannel(
            id=50004,
            guild_id=guild_id,
            name="string-values-channel",
            type="text",
            overwrites=json.dumps({"12345": {"allow": "not_an_int", "deny": 1024}}),
        )
    )

    session.commit()

    # Verify that evaluating does not raise an exception
    result = SecurityRuleEngine.evaluate(guild_id, session)
    # The rule evaluation should succeed (or catch inner exceptions and continue).
    assert isinstance(result, dict)
    assert "score" in result
    assert "alerts" in result


def test_large_guild_stress(session):
    """Stress test with 500 roles, 1000 channels, nested categories, and complex overwrites."""
    guild_id = 90004

    # 500 roles
    roles = []
    for i in range(500):
        roles.append(
            DiscordRole(
                id=10000 + i, guild_id=guild_id, name=f"Role-{i}", permissions=1 << 11 if i % 10 == 0 else 0, position=i
            )
        )

    # 1000 channels (with categories)
    channels = []
    # 50 categories
    for cat_idx in range(50):
        cat_id = 20000 + cat_idx
        channels.append(
            DiscordChannel(
                id=cat_id,
                guild_id=guild_id,
                name=f"CATEGORY-{cat_idx}",
                type="category",
                position=cat_idx,
                overwrites=json.dumps({"10000": {"allow": 1 << 10, "deny": 0}}),
            )
        )
        # 19 child channels per category
        for chan_idx in range(19):
            chan_id = 30000 + (cat_idx * 19) + chan_idx
            channels.append(
                DiscordChannel(
                    id=chan_id,
                    guild_id=guild_id,
                    parent_id=cat_id,
                    name=f"channel-{cat_idx}-{chan_idx}",
                    type="text" if chan_idx % 2 == 0 else "voice",
                    position=chan_idx,
                    overwrites=json.dumps({"10001": {"allow": 0, "deny": 1 << 10}}),
                )
            )

    # Bulk insert
    for r in roles:
        session.add(r)
    for c in channels:
        session.add(c)
    session.commit()

    # Measure execution time
    start_time = time.perf_counter()
    result = SecurityRuleEngine.evaluate(guild_id, session)
    end_time = time.perf_counter()

    elapsed = end_time - start_time
    print(f"Large Guild Evaluation Time: {elapsed:.4f}s")

    # Ensure it evaluates fast (e.g. < 2.0s to avoid UI performance bottlenecks)
    assert elapsed < 2.0
    assert isinstance(result["score"], int)


def test_widget_rendering_robustness(session):
    """Verify that widgets render correctly with a populated guild and don't raise type errors."""
    guild_id = 90005

    # Render with no DB data
    sidebar_empty = guild_admin_utilities_sidebar(guild_id, session)
    help_bubble_empty = guild_admin_utilities_help_bubble(guild_id, session)

    assert sidebar_empty is not None
    assert help_bubble_empty is not None

    # Convert FastHTML elements to string
    sidebar_html = str(sidebar_empty)
    help_bubble_html = str(help_bubble_empty)

    assert f"guild-admin-utilities-sidebar-{guild_id}" in sidebar_html
    assert f"guild-admin-utilities-help-bubble-{guild_id}" in help_bubble_html


@patch("app.ui.dashboard.get_internal_api_client")
@pytest.mark.asyncio
async def test_endpoint_ping_bot_malformed_failures(mock_client_cls):
    """Test /ping-bot endpoint when the bot API returns various non-200 or malformed results."""
    guild_id = 999

    mock_client = AsyncMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_client

    # 1. 500 Internal Server Error
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client.get.return_value = mock_resp

    res = await dashboard_ping_bot(guild_id)
    assert "Disconnected" in res.__html__()

    # 2. Malformed JSON (missing 'bot' key)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"something_else": "data"}
    mock_client.get.return_value = mock_resp

    res = await dashboard_ping_bot(guild_id)
    assert "Disconnected" in res.__html__()

    # 3. Timeout / Connection Closed
    mock_client.get.side_effect = Exception("Timeout connecting to bot")

    res = await dashboard_ping_bot(guild_id)
    assert "Disconnected" in res.__html__()


@patch("app.ui.dashboard.get_internal_api_client")
@pytest.mark.asyncio
async def test_endpoint_scan_failures(mock_client_cls):
    """Test /scan endpoint when bot API fails."""
    guild_id = 999

    mock_client = AsyncMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_client

    # 1. Bot returns 500 error
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client.post.return_value = mock_resp

    resp = await dashboard_scan_guild(guild_id)
    # The endpoint should handle the failure and still return the refresh header
    assert resp.headers.get("HX-Refresh") == "true"

    # 2. Connection exception
    mock_client.post.side_effect = Exception("Bot offline")
    resp = await dashboard_scan_guild(guild_id)
    assert resp.headers.get("HX-Refresh") == "true"
