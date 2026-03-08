import json
from unittest.mock import patch

import pytest
from fasthtml.common import FT, to_xml

from app.db.models import DiscordChannel
from app.extensions.utilities.widget import guild_admin_audit_channels_widget

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit

# Test Data
MOCK_GUILD_ID = 123456789


@pytest.fixture
def mock_session():
    with patch("app.extensions.utilities.widget.Session") as MockSession:
        yield MockSession.return_value.__enter__.return_value


@pytest.fixture
def mock_engine():
    with patch("app.extensions.utilities.widget.engine"):
        yield


def test_guild_admin_audit_channels_widget_empty(mock_session, mock_engine):
    mock_session.exec.return_value.all.return_value = []

    result = guild_admin_audit_channels_widget(MOCK_GUILD_ID)

    assert isinstance(result, FT)
    assert result.tag == "div"
    assert "Start Audit to view Channels" in str(result)
    assert "No channels found for this server." in str(result)


def test_guild_admin_audit_channels_widget_with_channels(mock_session, mock_engine):
    channels = [
        DiscordChannel(
            id=1,
            guild_id=MOCK_GUILD_ID,
            name="Category 1",
            type="category",
            position=1,
            overwrites=json.dumps({"123": {"allow": 1024, "deny": 0, "name": "Role A"}}),
        ),
        DiscordChannel(
            id=2,
            guild_id=MOCK_GUILD_ID,
            name="Channel 1",
            type="text",
            position=2,
            parent_id=1,
            overwrites=json.dumps({"456": {"allow": 2048, "deny": 1024, "name": "Role B"}}),
        ),
        DiscordChannel(
            id=3, guild_id=MOCK_GUILD_ID, name="Uncategorized Channel", type="text", position=3, overwrites=None
        ),
    ]
    mock_session.exec.return_value.all.return_value = channels

    result = guild_admin_audit_channels_widget(MOCK_GUILD_ID)

    html_output = to_xml(result)

    # Check overall rendering
    assert "Guild Channels" in html_output
    assert "CATEGORY 1" in html_output
    assert "Channel 1" in html_output
    assert "Uncategorized Channel" in html_output

    # Check for overrites UI rendering targets
    assert "Role A" in html_output
    assert "Role B" in html_output

    # Check for specific permissions UI
    assert "View Channel" in html_output  # Permission 1024 is View Channel
    assert "Send Messages" in html_output  # Permission 2048 is Send Messages


def test_guild_admin_audit_channels_widget_synced_channel(mock_session, mock_engine):
    overwrites_data = json.dumps({"123": {"allow": 1024, "deny": 0, "name": "Role A"}})
    channels = [
        DiscordChannel(
            id=1, guild_id=MOCK_GUILD_ID, name="Category 1", type="category", position=1, overwrites=overwrites_data
        ),
        DiscordChannel(
            id=2,
            guild_id=MOCK_GUILD_ID,
            name="Channel 1",
            type="text",
            position=2,
            parent_id=1,
            overwrites=overwrites_data,
        ),
    ]
    mock_session.exec.return_value.all.return_value = channels

    result = guild_admin_audit_channels_widget(MOCK_GUILD_ID)
    html_output = to_xml(result)

    # Should say synced
    assert "Synced" in html_output
    # Only one role A target should be listed in the overwrites logic (under category)
    assert html_output.count("Role A") == 2  # 1 in summary badge, 1 in details expanding header


def test_guild_admin_audit_channels_widget_private_channel(mock_session, mock_engine):
    # 1 << 10 is View Channel (deny makes it private for @everyone)
    overwrites_data = json.dumps({str(MOCK_GUILD_ID): {"allow": 0, "deny": 1 << 10, "name": "@everyone"}})
    channels = [
        DiscordChannel(
            id=2,
            guild_id=MOCK_GUILD_ID,
            name="Secret Channel",
            type="text",
            position=2,
            parent_id=None,
            overwrites=overwrites_data,
        ),
    ]
    mock_session.exec.return_value.all.return_value = channels

    result = guild_admin_audit_channels_widget(MOCK_GUILD_ID)
    html_output = to_xml(result)

    # Should have lock icon and error text class
    assert "🔒" in html_output
    assert "text-error" in html_output
