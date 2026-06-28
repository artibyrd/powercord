import json

import pytest
from sqlmodel import Session

from app.db.models import DiscordAuditorConfig, DiscordChannel, DiscordRole, GuildExtensionSettings
from app.extensions.utilities.widget import (
    CategoryPermissionBaseline,
    ExposedStaffChannels,
    GeneralRoleMentionability,
    LowTierRolePrivileges,
    OverPrivilegedBotIntegrations,
    PublicAnnouncementProtection,
    SecurityRuleEngine,
    SuggestiveHoneypotIntegration,
    UnauthorizedChatPings,
)

try:
    from app.extensions.honeypot.blueprint import HoneypotChannel
except ImportError:
    HoneypotChannel = None  # type: ignore[misc,assignment]


@pytest.fixture(autouse=True)
def clean_db(session: Session):
    from sqlalchemy import text

    def do_clean():
        session.execute(text("DELETE FROM discord_channels;"))
        session.execute(text("DELETE FROM discord_roles;"))
        session.execute(text("DELETE FROM discord_auditor_configs;"))
        session.execute(text("DELETE FROM guild_extension_settings;"))
        session.execute(text("DELETE FROM site_settings;"))
        session.execute(text("DELETE FROM user_settings;"))
        try:
            from sqlalchemy import inspect

            bind = session.get_bind()
            if inspect(bind).has_table("honeypot_channels"):
                session.execute(text("DELETE FROM honeypot_channels;"))
        except Exception:
            session.rollback()
        session.commit()

    do_clean()
    yield
    do_clean()


def test_category_permission_baseline(session: Session):
    guild_id = 12345

    # Create parent category
    parent = DiscordChannel(
        id=100,
        guild_id=guild_id,
        parent_id=None,
        name="Category",
        type="category",
        overwrites=json.dumps(
            {
                "999": {"allow": 0, "deny": 1 << 10}  # Deny view channel
            }
        ),
    )
    # Create child channel (exposed: allows view channel)
    child_exposed = DiscordChannel(
        id=101,
        guild_id=guild_id,
        parent_id=100,
        name="exposed-channel",
        type="text",
        overwrites=json.dumps(
            {
                "999": {"allow": 1 << 10, "deny": 0}  # Allow view channel
            }
        ),
    )
    # Create child channel (secure: inherits or denies)
    child_secure = DiscordChannel(
        id=102,
        guild_id=guild_id,
        parent_id=100,
        name="secure-channel",
        type="text",
        overwrites=json.dumps({"999": {"allow": 0, "deny": 1 << 10}}),
    )

    session.add_all([parent, child_exposed, child_secure])
    session.commit()

    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)

    # Should flag child_exposed but not child_secure
    assert len(alerts) == 1
    assert alerts[0]["rule"] == "Category Permission Baseline"
    assert alerts[0]["severity"] == "high"  # view_channel is leaked
    assert "exposed-channel" in alerts[0]["message"]

    # Assert details formatting & fallback ID
    assert "Target ID 999 has less restricted overwrites" in alerts[0]["details"]
    assert "Leaked allows: 'View Channel'" in alerts[0]["details"]
    assert "leaked denies: 'View Channel'" in alerts[0]["details"]


def test_category_permission_baseline_fully_synced(session: Session):
    guild_id = 12345
    parent = DiscordChannel(
        id=100,
        guild_id=guild_id,
        parent_id=None,
        name="Category",
        type="category",
        overwrites=json.dumps({"999": {"allow": 0, "deny": 1 << 10}}),
    )
    # Completely empty overwrites (synced, inherits deny)
    child_synced = DiscordChannel(
        id=101, guild_id=guild_id, parent_id=100, name="synced-channel", type="text", overwrites="{}"
    )
    session.add_all([parent, child_synced])
    session.commit()
    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)
    assert len(alerts) == 0


def test_category_permission_baseline_details_formatting(session: Session):
    guild_id = 12345

    # 1. Create a role in DB that matches the target ID
    role_resolved = DiscordRole(id=111, guild_id=guild_id, name="MyResolvedRole", permissions=0, position=1)

    # 2. Add channels with overwrites
    parent = DiscordChannel(
        id=100,
        guild_id=guild_id,
        parent_id=None,
        name="Category",
        type="category",
        overwrites=json.dumps(
            {
                "111": {"allow": 0, "deny": 1 << 10},  # Role resolved from DB
                "222": {"allow": 0, "deny": 1 << 10},  # Role resolved from metadata name & type
                "333": {"allow": 0, "deny": 1 << 10},  # Member resolved from metadata name & type
                "444": {"allow": 0, "deny": 1 << 10},  # Role fallback (no name but type = role)
                "555": {"allow": 0, "deny": 1 << 10},  # Member fallback (no name but type = member)
                "666": {"allow": 0, "deny": 1 << 10},  # Default fallback (no metadata)
            }
        ),
    )

    child = DiscordChannel(
        id=101,
        guild_id=guild_id,
        parent_id=100,
        name="exposed",
        type="text",
        overwrites=json.dumps(
            {
                "111": {"allow": 1 << 10, "deny": 0},
                "222": {"allow": 1 << 10, "deny": 0, "type": "role", "name": "MetadataRole"},
                "333": {"allow": 1 << 10, "deny": 0, "type": "member", "name": "MetadataMember"},
                "444": {"allow": 1 << 10, "deny": 0, "type": "role"},
                "555": {"allow": 1 << 10, "deny": 0, "type": "member"},
                "666": {"allow": 1 << 10, "deny": 0},
            }
        ),
    )

    session.add_all([role_resolved, parent, child])
    session.commit()

    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)

    # We expect 6 alerts, check the details string of each by matching the target ID or name
    details_map = {}
    for alert in alerts:
        details = alert["details"]
        if "MyResolvedRole" in details:
            details_map["111"] = details
        elif "MetadataRole" in details:
            details_map["222"] = details
        elif "MetadataMember" in details:
            details_map["333"] = details
        elif "444" in details:
            details_map["444"] = details
        elif "555" in details:
            details_map["555"] = details
        elif "666" in details:
            details_map["666"] = details

    assert (
        "Target Role 'MyResolvedRole' has less restricted overwrites. Leaked allows: 'View Channel', leaked denies: 'View Channel'."
        in details_map["111"]
    )
    assert (
        "Target Role 'MetadataRole' has less restricted overwrites. Leaked allows: 'View Channel', leaked denies: 'View Channel'."
        in details_map["222"]
    )
    assert (
        "Target Member 'MetadataMember' has less restricted overwrites. Leaked allows: 'View Channel', leaked denies: 'View Channel'."
        in details_map["333"]
    )
    assert (
        "Target Role ID 444 has less restricted overwrites. Leaked allows: 'View Channel', leaked denies: 'View Channel'."
        in details_map["444"]
    )
    assert (
        "Target Member ID 555 has less restricted overwrites. Leaked allows: 'View Channel', leaked denies: 'View Channel'."
        in details_map["555"]
    )
    assert (
        "Target ID 666 has less restricted overwrites. Leaked allows: 'View Channel', leaked denies: 'View Channel'."
        in details_map["666"]
    )


def test_public_announcement_protection(session: Session):

    guild_id = 12345

    # Configure auditor
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900, announcement_channel_ids="[201]")

    # Roles
    everyone = DiscordRole(id=guild_id, guild_id=guild_id, name="@everyone", permissions=0, position=0)
    low_role = DiscordRole(id=222, guild_id=guild_id, name="Members", permissions=0, position=1)
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)

    # Channels — grant View Channel + Send Messages so the alert fires
    ann_channel = DiscordChannel(
        id=201,
        guild_id=guild_id,
        parent_id=None,
        name="rules",
        type="text",
        overwrites=json.dumps(
            {
                "222": {"allow": (1 << 10) | (1 << 11), "deny": 0}  # View Channel + Send Messages
            }
        ),
    )

    session.add_all([config, everyone, low_role, sep_role, ann_channel])
    session.commit()

    rule = PublicAnnouncementProtection()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) > 0
    ann_alerts = [a for a in alerts if a["rule"] == "Public Announcement Protection"]
    assert len(ann_alerts) == 1
    assert "has effective permissions" in ann_alerts[0]["details"]
    assert "Send Messages" in ann_alerts[0]["details"]


def test_announcement_admin_bypass(session: Session):
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900, announcement_channel_ids="[201]")
    everyone = DiscordRole(id=guild_id, guild_id=guild_id, name="@everyone", permissions=0, position=0)
    low_admin = DiscordRole(id=111, guild_id=guild_id, name="Low Admin", permissions=1 << 3, position=1)
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    ann_channel = DiscordChannel(
        id=201,
        guild_id=guild_id,
        parent_id=None,
        name="announcements",
        type="text",
        overwrites=json.dumps({"111": {"allow": 0, "deny": 1 << 11}}),
    )
    session.add_all([config, everyone, low_admin, sep_role, ann_channel])
    session.commit()
    rule = PublicAnnouncementProtection()
    alerts = rule.evaluate(guild_id, session)
    assert len(alerts) > 0


def test_public_announcement_no_alert_when_view_channel_denied(session: Session):
    """@everyone has Send Messages in base permissions but View Channel is denied on the channel -> no alert."""
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900, announcement_channel_ids="[201]")
    everyone = DiscordRole(
        id=guild_id, guild_id=guild_id, name="@everyone", permissions=(1 << 10) | (1 << 11), position=0
    )
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    ann_channel = DiscordChannel(
        id=201,
        guild_id=guild_id,
        parent_id=None,
        name="announcements",
        type="text",
        overwrites=json.dumps({str(guild_id): {"allow": 0, "deny": 1 << 10}}),  # Deny View Channel
    )
    session.add_all([config, everyone, sep_role, ann_channel])
    session.commit()
    rule = PublicAnnouncementProtection()
    alerts = rule.evaluate(guild_id, session)
    assert len(alerts) == 0


def test_public_announcement_no_alert_when_category_denies_view(session: Session):
    """Announcement channel has no overwrites, but parent category denies View Channel -> no alert."""
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900, announcement_channel_ids="[201]")
    everyone = DiscordRole(
        id=guild_id, guild_id=guild_id, name="@everyone", permissions=(1 << 10) | (1 << 11), position=0
    )
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    category = DiscordChannel(
        id=100,
        guild_id=guild_id,
        parent_id=None,
        name="Staff Category",
        type="category",
        overwrites=json.dumps({str(guild_id): {"allow": 0, "deny": 1 << 10}}),  # Category denies View Channel
    )
    ann_channel = DiscordChannel(
        id=201,
        guild_id=guild_id,
        parent_id=100,
        name="announcements",
        type="text",
        overwrites="{}",  # No channel-level overwrites — inherits category deny
    )
    session.add_all([config, everyone, sep_role, category, ann_channel])
    session.commit()
    rule = PublicAnnouncementProtection()
    alerts = rule.evaluate(guild_id, session)
    assert len(alerts) == 0


def test_public_announcement_alert_when_view_channel_allowed(session: Session):
    """Role can see the channel AND has Send Messages -> alert fires (regression guard)."""
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900, announcement_channel_ids="[201]")
    everyone = DiscordRole(
        id=guild_id, guild_id=guild_id, name="@everyone", permissions=(1 << 10) | (1 << 11), position=0
    )
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    ann_channel = DiscordChannel(
        id=201,
        guild_id=guild_id,
        parent_id=None,
        name="announcements",
        type="text",
        overwrites="{}",  # No overwrites — base permissions include View Channel + Send Messages
    )
    session.add_all([config, everyone, sep_role, ann_channel])
    session.commit()
    rule = PublicAnnouncementProtection()
    alerts = rule.evaluate(guild_id, session)
    assert len(alerts) == 1
    assert "@everyone" in alerts[0]["message"]
    assert "Send Messages" in alerts[0]["details"]


def test_exposed_staff_channels(session: Session):
    guild_id = 12345

    # Config
    config = DiscordAuditorConfig(guild_id=guild_id, staff_channel_ids="[301]")

    # @everyone with View Channel in base permissions (realistic Discord default)
    everyone = DiscordRole(id=guild_id, guild_id=guild_id, name="@everyone", permissions=1 << 10, position=0)

    # Staff channel that doesn't explicitly deny view_channel
    channel_exposed = DiscordChannel(
        id=301, guild_id=guild_id, parent_id=None, name="admin-talk", type="text", overwrites="{}"
    )
    # Staff channel that denies view_channel to @everyone
    channel_secure = DiscordChannel(
        id=302,
        guild_id=guild_id,
        parent_id=None,
        name="staff-only",
        type="text",
        overwrites=json.dumps({str(guild_id): {"allow": 0, "deny": 1 << 10}}),
    )

    session.add_all([config, everyone, channel_exposed, channel_secure])
    session.commit()

    rule = ExposedStaffChannels()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert alerts[0]["message"] == "Staff channel #admin-talk is visible to @everyone."


def test_exposed_staff_channels_non_staff_role_and_sync(session: Session):
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_channel_ids="[301, 302, 303]", staff_separator_role_id=900)
    everyone = DiscordRole(id=guild_id, guild_id=guild_id, name="@everyone", permissions=0, position=0)
    non_staff = DiscordRole(id=111, guild_id=guild_id, name="Members", permissions=0, position=1)
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    category = DiscordChannel(
        id=100,
        guild_id=guild_id,
        parent_id=None,
        name="Staff Category",
        type="category",
        overwrites=json.dumps({str(guild_id): {"allow": 0, "deny": 1 << 10}}),
    )
    chan_synced = DiscordChannel(
        id=301, guild_id=guild_id, parent_id=100, name="staff-synced", type="text", overwrites="{}"
    )
    chan_exposed_role = DiscordChannel(
        id=302,
        guild_id=guild_id,
        parent_id=100,
        name="staff-exposed-role",
        type="text",
        overwrites=json.dumps({str(guild_id): {"allow": 0, "deny": 1 << 10}, "111": {"allow": 1 << 10, "deny": 0}}),
    )
    chan_secure = DiscordChannel(
        id=303,
        guild_id=guild_id,
        parent_id=100,
        name="staff-secure",
        type="text",
        overwrites=json.dumps({str(guild_id): {"allow": 0, "deny": 1 << 10}, "111": {"allow": 0, "deny": 1 << 10}}),
    )
    session.add_all([config, everyone, non_staff, sep_role, category, chan_synced, chan_exposed_role, chan_secure])
    session.commit()
    rule = ExposedStaffChannels()
    alerts = rule.evaluate(guild_id, session)
    assert len(alerts) == 1
    assert alerts[0]["message"] == "Staff channel #staff-exposed-role is visible to Members."


def test_unauthorized_chat_pings(session: Session):
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900)
    everyone = DiscordRole(id=guild_id, guild_id=guild_id, name="@everyone", permissions=0, position=0)
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)

    # Voice channel allowing @everyone to View Channel + Send Messages
    voice_chan = DiscordChannel(
        id=401,
        guild_id=guild_id,
        parent_id=None,
        name="General Voice",
        type="voice",
        overwrites=json.dumps({str(guild_id): {"allow": (1 << 10) | (1 << 11), "deny": 0}}),
    )

    session.add_all([config, everyone, sep_role, voice_chan])
    session.commit()

    rule = UnauthorizedChatPings()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert alerts[0]["rule"] == "Unauthorized Chat Pings in Non-Text Locations"
    assert "Send Messages" in alerts[0]["details"]


def test_unauthorized_chat_pings_admin_bypass(session: Session):
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900)
    everyone = DiscordRole(id=guild_id, guild_id=guild_id, name="@everyone", permissions=0, position=0)
    low_admin = DiscordRole(id=111, guild_id=guild_id, name="Low Admin", permissions=1 << 3, position=1)
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    voice_chan = DiscordChannel(
        id=401,
        guild_id=guild_id,
        parent_id=None,
        name="General Voice",
        type="voice",
        overwrites=json.dumps({"111": {"allow": 0, "deny": 1 << 11}}),
    )
    session.add_all([config, everyone, low_admin, sep_role, voice_chan])
    session.commit()
    rule = UnauthorizedChatPings()
    alerts = rule.evaluate(guild_id, session)
    assert len(alerts) == 1
    assert "Low Admin" in alerts[0]["message"]


def test_unauthorized_chat_pings_no_alert_when_view_channel_denied(session: Session):
    """Voice channel allows Send Messages but View Channel is denied -> no alert."""
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900)
    everyone = DiscordRole(
        id=guild_id, guild_id=guild_id, name="@everyone", permissions=(1 << 10) | (1 << 11), position=0
    )
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    voice_chan = DiscordChannel(
        id=401,
        guild_id=guild_id,
        parent_id=None,
        name="General Voice",
        type="voice",
        overwrites=json.dumps({str(guild_id): {"allow": 0, "deny": 1 << 10}}),  # Deny View Channel
    )
    session.add_all([config, everyone, sep_role, voice_chan])
    session.commit()
    rule = UnauthorizedChatPings()
    alerts = rule.evaluate(guild_id, session)
    assert len(alerts) == 0


def test_unauthorized_chat_pings_category_inheritance(session: Session):
    """Voice channel inherits View Channel deny from parent category -> no alert."""
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900)
    everyone = DiscordRole(
        id=guild_id, guild_id=guild_id, name="@everyone", permissions=(1 << 10) | (1 << 11), position=0
    )
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    category = DiscordChannel(
        id=100,
        guild_id=guild_id,
        parent_id=None,
        name="Private Category",
        type="category",
        overwrites=json.dumps({str(guild_id): {"allow": 0, "deny": 1 << 10}}),
    )
    voice_chan = DiscordChannel(
        id=401,
        guild_id=guild_id,
        parent_id=100,
        name="General Voice",
        type="voice",
        overwrites="{}",  # No channel overwrites — inherits category deny
    )
    session.add_all([config, everyone, sep_role, category, voice_chan])
    session.commit()
    rule = UnauthorizedChatPings()
    alerts = rule.evaluate(guild_id, session)
    assert len(alerts) == 0


def test_low_tier_role_privileges(session: Session):
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900)
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)

    # Role below staff separator with Administrator
    low_role_admin = DiscordRole(id=501, guild_id=guild_id, name="Low Admin", permissions=1 << 3, position=2)
    # Role above staff separator with Administrator
    high_role_admin = DiscordRole(id=502, guild_id=guild_id, name="High Admin", permissions=1 << 3, position=7)

    session.add_all([config, sep_role, low_role_admin, high_role_admin])
    session.commit()

    rule = LowTierRolePrivileges()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert "Low Admin" in alerts[0]["message"]
    assert "has sensitive permissions: 'Administrator'." in alerts[0]["details"]


def test_general_role_mentionability(session: Session):
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900)
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)

    # Role below separator that is mentionable and not managed
    low_mentionable = DiscordRole(
        id=601,
        guild_id=guild_id,
        name="Pingable Role",
        permissions=0,
        position=2,
        is_mentionable=True,
        is_managed=False,
    )
    # Managed bot role that is mentionable
    bot_mentionable = DiscordRole(
        id=602, guild_id=guild_id, name="Bot Role", permissions=0, position=2, is_mentionable=True, is_managed=True
    )

    session.add_all([config, sep_role, low_mentionable, bot_mentionable])
    session.commit()

    rule = GeneralRoleMentionability()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert "Pingable Role" in alerts[0]["message"]


def test_suggestive_honeypot_integration(session: Session):
    guild_id = 12345

    # 1. Honeypot disabled -> returns tip suggestion
    rule = SuggestiveHoneypotIntegration()
    alerts = rule.evaluate(guild_id, session)
    assert len(alerts) == 1
    assert "Install the honeypot extension" in alerts[0]["message"]
    assert alerts[0]["severity"] == "low"

    # 2. Honeypot enabled -> checks public discovery channels
    ext_setting = GuildExtensionSettings(
        guild_id=guild_id, extension_name="honeypot", gadget_type="cog", is_enabled=True
    )

    disc_channel = DiscordChannel(
        id=701, guild_id=guild_id, parent_id=None, name="public-discovery", type="text", overwrites="{}"
    )

    session.add(ext_setting)
    session.add(disc_channel)
    session.commit()

    alerts2 = rule.evaluate(guild_id, session)
    assert len(alerts2) == 1
    assert "unprotected" in alerts2[0]["message"]
    assert len(alerts2[0]["action_buttons"]) == 3

    # 3. Add to HoneypotChannel -> should be protected
    if HoneypotChannel is not None:
        protected = HoneypotChannel(guild_id=guild_id, channel_id=701)
        session.add(protected)
        session.commit()

        alerts3 = rule.evaluate(guild_id, session)
        assert len(alerts3) == 0


def test_over_privileged_bot_integrations(session: Session):
    guild_id = 12345

    # Managed bot role with Administrator
    bot_role = DiscordRole(
        id=801, guild_id=guild_id, name="Overprivileged Bot", permissions=1 << 3, position=4, is_managed=True
    )
    # Standard role with Administrator
    user_role = DiscordRole(
        id=802, guild_id=guild_id, name="Admin User", permissions=1 << 3, position=4, is_managed=False
    )

    session.add_all([bot_role, user_role])
    session.commit()

    rule = OverPrivilegedBotIntegrations()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert "Overprivileged Bot" in alerts[0]["message"]
    assert "has sensitive permissions: 'Administrator'." in alerts[0]["details"]


def test_security_rule_engine(session: Session):
    guild_id = 12345

    # Seed various issues
    # Low-tier role privilege (high severity - 15 points)
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900)
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    low_role_admin = DiscordRole(id=901, guild_id=guild_id, name="Low Admin", permissions=1 << 3, position=2)

    session.add_all([config, sep_role, low_role_admin])
    session.commit()

    engine = SecurityRuleEngine()
    result = engine.run_all(guild_id, session)

    # Expected alerts: LowTierRolePrivileges (high), SuggestiveHoneypotIntegration (low)
    # score = 100 - 15 (high) - 5 (low) = 80
    assert result["score"] == 80


def test_security_rule_engine_evaluate_caching(session: Session):
    guild_id = 12345

    # Seed DB
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900)
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)

    session.add_all([config, sep_role])
    session.commit()

    # Clear cache before starting
    SecurityRuleEngine._evaluation_cache.clear()

    # First evaluate
    res1 = SecurityRuleEngine.evaluate(guild_id, session)

    # Second evaluate (should hit cache)
    res2 = SecurityRuleEngine.evaluate(guild_id, session)
    assert res2 == res1

    # Verify that there is exactly one cached entry
    assert len(SecurityRuleEngine._evaluation_cache) == 1

    # Invalidate via the centralized method
    SecurityRuleEngine.invalidate(guild_id)
    assert len(SecurityRuleEngine._evaluation_cache) == 0

    # Re-evaluate after invalidation should re-run rules
    res3 = SecurityRuleEngine.evaluate(guild_id, session)
    assert res3 == res1  # Same DB state, same result


def test_category_baseline_inert_leak_annotation(session: Session):
    """Child channel allows Send Messages but also denies View Channel (matching parent) -> low severity + INERT marker."""
    guild_id = 12345

    parent = DiscordChannel(
        id=100,
        guild_id=guild_id,
        parent_id=None,
        name="Category",
        type="category",
        overwrites=json.dumps(
            {
                "999": {"allow": 0, "deny": 1 << 10}  # Deny View Channel at parent
            }
        ),
    )
    # Child allows Send Messages but ALSO denies View Channel (matching parent).
    # The Send Messages leak is inert because View Channel is denied.
    child = DiscordChannel(
        id=101,
        guild_id=guild_id,
        parent_id=100,
        name="restricted-channel",
        type="text",
        overwrites=json.dumps(
            {
                "999": {"allow": 1 << 11, "deny": 1 << 10}  # Allow Send Messages + Deny View Channel
            }
        ),
    )

    session.add_all([parent, child])
    session.commit()

    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert alerts[0]["severity"] == "low"
    assert "[INERT" in alerts[0]["details"]
    assert "View Channel denied" in alerts[0]["details"]
    assert "Send Messages" in alerts[0]["details"]


def test_category_baseline_active_leak_not_annotated(session: Session):
    """Child channel allows Send Messages AND View Channel is allowed -> normal severity, no INERT marker."""
    guild_id = 12345

    parent = DiscordChannel(
        id=100,
        guild_id=guild_id,
        parent_id=None,
        name="Category",
        type="category",
        overwrites=json.dumps(
            {
                "999": {"allow": 0, "deny": 0}  # No restrictions at parent
            }
        ),
    )
    # Child allows Send Messages; View Channel is NOT denied anywhere
    child = DiscordChannel(
        id=101,
        guild_id=guild_id,
        parent_id=100,
        name="open-channel",
        type="text",
        overwrites=json.dumps(
            {
                "999": {"allow": 1 << 11, "deny": 0}  # Allow Send Messages
            }
        ),
    )

    session.add_all([parent, child])
    session.commit()

    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)

    assert len(alerts) == 1
    assert alerts[0]["severity"] == "medium"  # Not downgraded
    assert "[INERT" not in alerts[0]["details"]


def test_security_rule_engine_checksum_caching(session: Session):
    """Verify that SecurityRuleEngine caching handles hits and misses correctly when DB is modified."""
    guild_id = 99999
    SecurityRuleEngine._evaluation_cache.clear()

    # Seed initial DB
    config = DiscordAuditorConfig(
        guild_id=guild_id,
        staff_separator_role_id=10,
        staff_channel_ids="[101]",
        announcement_channel_ids="[102]",
    )
    role = DiscordRole(
        id=10,
        guild_id=guild_id,
        name="Staff Separator",
        permissions=0,
        position=5,
    )
    channel = DiscordChannel(
        id=101,
        guild_id=guild_id,
        parent_id=None,
        name="staff-chat",
        type="text",
        overwrites="{}",
    )

    session.add_all([config, role, channel])
    session.commit()

    # 1. First evaluation - must compute and cache
    res1 = SecurityRuleEngine.evaluate(guild_id, session)
    assert len(SecurityRuleEngine._evaluation_cache) == 1

    # 2. Second evaluation (identical state) - must be a cache hit
    res2 = SecurityRuleEngine.evaluate(guild_id, session)
    assert res2 is res1  # cache hit returns the same object reference

    # 3. Modify channel overwrites (DB modification) - must result in cache miss
    channel.overwrites = '{"999": {"allow": 1024, "deny": 0}}'
    session.add(channel)
    session.commit()

    res3 = SecurityRuleEngine.evaluate(guild_id, session)
    assert res3 is not res1  # cache miss returns a new object reference

    # 4. Modify config values (DB modification) - must result in cache miss
    config.staff_channel_ids = "[101, 103]"
    session.add(config)
    session.commit()

    res4 = SecurityRuleEngine.evaluate(guild_id, session)
    assert res4 is not res3  # cache miss returns a new object reference


def test_parent_child_alert_linking(session: Session):
    from app.db.models import SecurityAlertOverride

    guild_id = 55555

    # 1. Setup base configuration
    config = DiscordAuditorConfig(
        guild_id=guild_id,
        staff_separator_role_id=10,  # Below position 10 is low-tier
        staff_channel_ids="[101]",
        announcement_channel_ids="[102]",
    )

    # 2. Setup roles
    # Low-tier role with Administrator (triggers Rule 5 parent)
    low_tier_admin = DiscordRole(
        id=2,
        guild_id=guild_id,
        name="LowTierAdmin",
        permissions=8,  # Administrator (1 << 3)
        position=5,  # Below separator role (5 < 10)
    )

    # Separator role
    sep_role = DiscordRole(
        id=10,
        guild_id=guild_id,
        name="Separator",
        permissions=0,
        position=10,
    )

    # Everyone role
    everyone_role = DiscordRole(
        id=guild_id,
        guild_id=guild_id,
        name="@everyone",
        permissions=0,
        position=0,
    )

    # Enable honeypot extension to prevent Rule 7 alert noise
    honeypot_ext = GuildExtensionSettings(
        guild_id=guild_id,
        extension_name="honeypot",
        gadget_type="cog",
        is_enabled=True,
    )

    # 3. Setup channels
    staff_chat = DiscordChannel(
        id=101,
        guild_id=guild_id,
        name="staff-chat",
        type="text",
        overwrites="{}",
    )

    announcement_chat = DiscordChannel(
        id=102,
        guild_id=guild_id,
        name="announcements",
        type="news",
        overwrites="{}",
    )

    session.add_all([config, low_tier_admin, sep_role, everyone_role, honeypot_ext, staff_chat, announcement_chat])
    session.commit()

    # Clear cache before evaluating
    SecurityRuleEngine._evaluation_cache.clear()

    # Run evaluation
    res = SecurityRuleEngine.evaluate(guild_id, session, include_overridden=True)
    alerts = res["alerts"]

    # We expect:
    # 1. Rule 5 (Low-Tier Role Privileges) for "LowTierAdmin"
    # 2. Rule 3 (Exposed Staff Channels) for "LowTierAdmin"
    # 3. Rule 2 (Public Announcement Protection) for "LowTierAdmin"

    r5_alert = next((a for a in alerts if a["rule"] == "Low-Tier Role Privileges"), None)
    r3_alert = next((a for a in alerts if a["rule"] == "Exposed Staff Channels"), None)
    r2_alert = next((a for a in alerts if a["rule"] == "Public Announcement Protection"), None)

    assert r5_alert is not None
    assert r3_alert is not None
    assert r2_alert is not None

    # Check linkage
    assert r5_alert["child_count"] == 2
    assert r3_alert["parent_hash"] == r5_alert["alert_hash"]
    assert r2_alert["parent_hash"] == r5_alert["alert_hash"]

    # Score checks:
    # Since r3 and r2 are child alerts of r5, and r5 is active (not overridden),
    # r3 and r2 must be excluded from the score computation.
    # Score calculation: 100 - (15 * NumHigh).
    # Since r5 is High severity and the only counted alert:
    # Expected score = 100 - 15 = 85.
    assert res["score"] == 85

    # 4. Test Overridden Parent Behavior
    # Override the parent (Rule 5)
    parent_override = SecurityAlertOverride(
        guild_id=guild_id,
        alert_hash=r5_alert["alert_hash"],
        rule=r5_alert["rule"],
        category=r5_alert["category"],
        message=r5_alert["message"],
        comment="Parent override test",
    )
    session.add(parent_override)
    session.commit()

    # Clear cache and evaluate with overrides applied (include_overridden=False)
    SecurityRuleEngine._evaluation_cache.clear()
    res_override = SecurityRuleEngine.evaluate(guild_id, session, include_overridden=False)
    active_alerts = res_override["alerts"]

    # Parent (r5) should be filtered out
    assert not any(a["alert_hash"] == r5_alert["alert_hash"] for a in active_alerts)

    # Children (r3 and r2) should still be active
    r3_active = next((a for a in active_alerts if a["alert_hash"] == r3_alert["alert_hash"]), None)
    r2_active = next((a for a in active_alerts if a["alert_hash"] == r2_alert["alert_hash"]), None)

    assert r3_active is not None
    assert r2_active is not None

    # Since parent is overridden (filtered out), the children should lose their active parent status
    # in score computation, meaning they revert to being counted individually.
    # Both are High severity. Penalty = 15 + 15 = 30.
    # Expected score = 100 - 30 = 70.
    assert res_override["score"] == 70


def test_parent_child_alert_linking_mention_everyone(session: Session):
    guild_id = 66666

    config = DiscordAuditorConfig(
        guild_id=guild_id,
        staff_separator_role_id=10,
        staff_channel_ids="[]",
        announcement_channel_ids="[]",
    )

    # Low-tier role with Mention Everyone (triggers Rule 5) and is mentionable (triggers Rule 6)
    low_tier_role = DiscordRole(
        id=3,
        guild_id=guild_id,
        name="LowTierPingable",
        permissions=131072,  # Mention Everyone (1 << 17)
        position=5,
        is_managed=False,
        is_mentionable=True,  # Mentionable (triggers Rule 6)
    )

    sep_role = DiscordRole(
        id=10,
        guild_id=guild_id,
        name="Separator",
        permissions=0,
        position=10,
    )

    everyone_role = DiscordRole(
        id=guild_id,
        guild_id=guild_id,
        name="@everyone",
        permissions=0,
        position=0,
    )

    honeypot_ext = GuildExtensionSettings(
        guild_id=guild_id,
        extension_name="honeypot",
        gadget_type="cog",
        is_enabled=True,
    )

    session.add_all([config, low_tier_role, sep_role, everyone_role, honeypot_ext])
    session.commit()

    SecurityRuleEngine._evaluation_cache.clear()
    res = SecurityRuleEngine.evaluate(guild_id, session, include_overridden=True)
    alerts = res["alerts"]

    # We expect:
    # 1. Rule 5 (Low-Tier Role Privileges) for "LowTierPingable" (High severity)
    # 2. Rule 6 (General Role Mentionability) for "LowTierPingable" (Low severity)

    r5_alert = next((a for a in alerts if a["rule"] == "Low-Tier Role Privileges"), None)
    r6_alert = next((a for a in alerts if a["rule"] == "General Role Mentionability"), None)

    assert r5_alert is not None
    assert r6_alert is not None

    # Check linkage
    assert r5_alert["child_count"] == 1
    assert r6_alert["parent_hash"] == r5_alert["alert_hash"]

    # Score checks:
    # r6 (Low severity) is excluded since r5 is active.
    # Score penalty = 15 (r5 is High).
    # Expected score = 100 - 15 = 85.
    assert res["score"] == 85


def test_parent_child_alerts_rendering():
    from fasthtml.common import to_xml

    from app.extensions.utilities.widget import _render_alerts_list

    parent_hash = "parent123"
    alerts = [
        {
            "rule": "Low-Tier Role Privileges",
            "category": "roles",
            "severity": "high",
            "message": "Low-tier role has sensitive permissions.",
            "alert_hash": parent_hash,
            "child_count": 1,
            "parent_hash": None,
        },
        {
            "rule": "Exposed Staff Channels",
            "category": "exposure",
            "severity": "high",
            "message": "Staff channel is visible.",
            "alert_hash": "child456",
            "child_count": 0,
            "parent_hash": parent_hash,
            "parent_rule": "Low-Tier Role Privileges",
        },
    ]

    active_hashes = {a["alert_hash"] for a in alerts}

    # Case 1: Both visible (e.g. All tab)
    html_all = to_xml(_render_alerts_list(alerts, guild_id=123, active_hashes=active_hashes))
    # Child should be indented (ml-8), dashed (border-dashed), and show "Cascaded from"
    assert "ml-8" in html_all
    assert "border-dashed" in html_all
    assert "Cascaded from: Low-Tier Role Privileges" in html_all

    # Case 2: Parent filtered out (e.g. Exposure tab)
    filtered_alerts = [alerts[1]]
    html_filtered = to_xml(_render_alerts_list(filtered_alerts, guild_id=123, active_hashes=active_hashes))
    # Child should NOT be indented (no ml-8), but STILL be dashed (border-dashed) and show "Associated with upstream alert"
    assert "ml-8" not in html_filtered
    assert "border-dashed" in html_filtered
    assert "Associated with upstream alert: Low-Tier Role Privileges" in html_filtered
