import json
from unittest.mock import MagicMock

import pytest

from app.common.discord_constants import ALL_PERMISSIONS
from app.db.models import DiscordChannel, DiscordRole
from app.extensions.utilities.widget import CategoryPermissionBaseline, decode_permissions

# Mark this module as unit tests
pytestmark = pytest.mark.unit


class MockSession:
    """A database-free mock of the SQLModel Session that returns predefined channels and roles."""

    def __init__(self, channels, roles):
        self.channels = channels
        self.roles = roles
        self._exec_calls = 0

    def exec(self, query):
        self._exec_calls += 1
        mock_result = MagicMock()
        if self._exec_calls == 1:
            # First select query is for channels
            mock_result.all.return_value = self.channels
        else:
            # Second select query is for roles
            mock_result.all.return_value = self.roles
        return mock_result


def test_decode_permissions_zero():
    """Verify that permission bitmask of 0 decodes to 'none'."""
    assert decode_permissions(0) == "none"


def test_decode_permissions_single_bit():
    """Verify that a single permission bit decodes to its single-quoted name."""
    # 1 << 3 is Administrator
    assert decode_permissions(1 << 3) == "'Administrator'"


def test_decode_permissions_multiple_bits():
    """Verify that multiple active permission bits decode to comma-separated single-quoted names."""
    # 1<<3 (Administrator), 1<<17 (Mention Everyone), 1<<11 (Send Messages)
    mask = (1 << 3) | (1 << 17) | (1 << 11)

    # Let's dynamically find the expected output based on insertion order of ALL_PERMISSIONS
    expected_active = []
    for name, value in ALL_PERMISSIONS.items():
        if (mask & value) == value:
            expected_active.append(f"'{name}'")
    expected_str = ", ".join(expected_active)

    assert decode_permissions(mask) == expected_str
    # Verify exact expected ordering based on SENSITIVE_PERMISSIONS then OTHER_PERMISSIONS
    assert expected_active == ["'Administrator'", "'Mention Everyone'", "'Send Messages'"]


def test_decode_permissions_max_integer():
    """Verify that maximum integer value maps to all defined permissions without crash."""
    # Using a huge integer (all bits set to 1)
    max_val = (1 << 128) - 1
    decoded = decode_permissions(max_val)

    # It should match all keys in ALL_PERMISSIONS
    for name in ALL_PERMISSIONS.keys():
        assert f"'{name}'" in decoded


def test_decode_permissions_unrecognized_bits():
    """Verify that unrecognized bits are ignored by decoding logic."""
    # Bit 50 is not in ALL_PERMISSIONS
    unrecognized_bit = 1 << 50
    assert decode_permissions(unrecognized_bit) == "none"

    # Combined unrecognized + recognized bit
    combined = unrecognized_bit | (1 << 3)
    assert decode_permissions(combined) == "'Administrator'"


def test_target_name_resolution_prefetched_role_map():
    """Case A: Target ID is in pre-fetched role map."""
    guild_id = 112201
    target_id = 999

    role = DiscordRole(
        id=target_id,
        guild_id=guild_id,
        name="Prefetched Role Name",
        position=1,
        permissions=0,
    )

    parent = DiscordChannel(
        id=100,
        guild_id=guild_id,
        parent_id=None,
        name="Category Parent",
        type="category",
        overwrites=json.dumps({str(target_id): {"allow": 0, "deny": 1 << 10}}),
    )

    child = DiscordChannel(
        id=101,
        guild_id=guild_id,
        parent_id=100,
        name="Child Channel",
        type="text",
        overwrites=json.dumps({str(target_id): {"allow": 1 << 10, "deny": 0}}),
    )

    session = MockSession(channels=[parent, child], roles=[role])
    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert "Target Role 'Prefetched Role Name' has less restricted overwrites" in alerts[0]["details"]


def test_target_name_resolution_metadata_role():
    """Case B: Target ID not in database, but metadata indicates type='role' and has name."""
    guild_id = 112202
    target_id = 888

    parent = DiscordChannel(
        id=200,
        guild_id=guild_id,
        parent_id=None,
        name="Category Parent",
        type="category",
        overwrites=json.dumps({str(target_id): {"allow": 0, "deny": 1 << 10}}),
    )

    child = DiscordChannel(
        id=201,
        guild_id=guild_id,
        parent_id=200,
        name="Child Channel",
        type="text",
        overwrites=json.dumps(
            {str(target_id): {"allow": 1 << 10, "deny": 0, "type": "role", "name": "Metadata Role Name"}}
        ),
    )

    session = MockSession(channels=[parent, child], roles=[])
    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert "Target Role 'Metadata Role Name' has less restricted overwrites" in alerts[0]["details"]


def test_target_name_resolution_metadata_member():
    """Case C: Target ID not in database, but metadata indicates type='member' and has name."""
    guild_id = 112203
    target_id = 777

    parent = DiscordChannel(
        id=300,
        guild_id=guild_id,
        parent_id=None,
        name="Category Parent",
        type="category",
        overwrites=json.dumps({str(target_id): {"allow": 0, "deny": 1 << 10}}),
    )

    child = DiscordChannel(
        id=301,
        guild_id=guild_id,
        parent_id=300,
        name="Child Channel",
        type="text",
        overwrites=json.dumps(
            {str(target_id): {"allow": 1 << 10, "deny": 0, "type": "member", "name": "Metadata Member Name"}}
        ),
    )

    session = MockSession(channels=[parent, child], roles=[])
    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert "Target Member 'Metadata Member Name' has less restricted overwrites" in alerts[0]["details"]


def test_target_name_resolution_metadata_fallback_id():
    """Case D: Target ID not in database, has name, but type is unrecognized."""
    guild_id = 112204
    target_id = 666

    parent = DiscordChannel(
        id=400,
        guild_id=guild_id,
        parent_id=None,
        name="Category Parent",
        type="category",
        overwrites=json.dumps({str(target_id): {"allow": 0, "deny": 1 << 10}}),
    )

    child = DiscordChannel(
        id=401,
        guild_id=guild_id,
        parent_id=400,
        name="Child Channel",
        type="text",
        overwrites=json.dumps(
            {str(target_id): {"allow": 1 << 10, "deny": 0, "type": "unrecognized_type", "name": "Fallback Name"}}
        ),
    )

    session = MockSession(channels=[parent, child], roles=[])
    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert "Target ID 'Fallback Name' has less restricted overwrites" in alerts[0]["details"]


def test_target_name_resolution_fallback_role_id():
    """Case E: Target ID not in database, no name, type='role'."""
    guild_id = 112205
    target_id = 555

    parent = DiscordChannel(
        id=500,
        guild_id=guild_id,
        parent_id=None,
        name="Category Parent",
        type="category",
        overwrites=json.dumps({str(target_id): {"allow": 0, "deny": 1 << 10}}),
    )

    child = DiscordChannel(
        id=501,
        guild_id=guild_id,
        parent_id=500,
        name="Child Channel",
        type="text",
        overwrites=json.dumps({str(target_id): {"allow": 1 << 10, "deny": 0, "type": "role"}}),
    )

    session = MockSession(channels=[parent, child], roles=[])
    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert "Target Role ID 555 has less restricted overwrites" in alerts[0]["details"]


def test_target_name_resolution_fallback_member_id():
    """Case F: Target ID not in database, no name, type='member'."""
    guild_id = 112206
    target_id = 444

    parent = DiscordChannel(
        id=600,
        guild_id=guild_id,
        parent_id=None,
        name="Category Parent",
        type="category",
        overwrites=json.dumps({str(target_id): {"allow": 0, "deny": 1 << 10}}),
    )

    child = DiscordChannel(
        id=601,
        guild_id=guild_id,
        parent_id=600,
        name="Child Channel",
        type="text",
        overwrites=json.dumps({str(target_id): {"allow": 1 << 10, "deny": 0, "type": "member"}}),
    )

    session = MockSession(channels=[parent, child], roles=[])
    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert "Target Member ID 444 has less restricted overwrites" in alerts[0]["details"]


def test_target_name_resolution_fallback_raw_id():
    """Case G: Target ID not in database, no name, unrecognized or absent type."""
    guild_id = 112207
    target_id = 333

    parent = DiscordChannel(
        id=700,
        guild_id=guild_id,
        parent_id=None,
        name="Category Parent",
        type="category",
        overwrites=json.dumps({str(target_id): {"allow": 0, "deny": 1 << 10}}),
    )

    child = DiscordChannel(
        id=701,
        guild_id=guild_id,
        parent_id=700,
        name="Child Channel",
        type="text",
        overwrites=json.dumps({str(target_id): {"allow": 1 << 10, "deny": 0, "type": "some_unknown_type"}}),
    )

    session = MockSession(channels=[parent, child], roles=[])
    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert "Target ID 333 has less restricted overwrites" in alerts[0]["details"]
