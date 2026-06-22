import pytest
from sqlmodel import Session

from app.db.models import DiscordAuditorConfig, DiscordRole, SecurityAlertOverride
from app.extensions.utilities.widget import SecurityRuleEngine

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clean_db(session: Session):
    from sqlalchemy import text

    def do_clean():
        session.execute(text("DELETE FROM discord_roles;"))
        session.execute(text("DELETE FROM discord_auditor_configs;"))
        session.execute(text("DELETE FROM security_alert_overrides;"))
        session.commit()

    do_clean()
    yield
    do_clean()


def test_security_alert_override_workflow(session: Session):
    guild_id = 999123

    # Setup separator role
    sep_role = DiscordRole(
        id=1,
        guild_id=guild_id,
        name="Separator",
        permissions=0,
        position=5,
        color=0,
        is_hoisted=False,
        is_managed=False,
        is_mentionable=False,
    )
    session.add(sep_role)

    # Setup low-tier role with Administrator (1 << 3) - Rule 5 violation
    low_role = DiscordRole(
        id=2,
        guild_id=guild_id,
        name="Violator",
        permissions=1 << 3,
        position=2,
        color=0,
        is_hoisted=False,
        is_managed=False,
        is_mentionable=False,
    )
    session.add(low_role)

    # Setup Auditor Config
    config = DiscordAuditorConfig(
        guild_id=guild_id,
        staff_separator_role_id=1,
        staff_channel_ids="[]",
        announcement_channel_ids="[]",
    )
    session.add(config)
    session.commit()

    # 1. Run audit initial - should have 1 alert and low score
    SecurityRuleEngine.invalidate(guild_id)
    evaluation = SecurityRuleEngine.evaluate(guild_id, session)
    alerts = evaluation["alerts"]
    score = evaluation["score"]

    assert len(alerts) == 1
    assert score < 100
    alert = alerts[0]
    alert_hash = alert.get("alert_hash")
    assert alert_hash is not None

    # 2. Add override
    override = SecurityAlertOverride(
        guild_id=guild_id,
        alert_hash=alert_hash,
        rule=alert["rule"],
        category=alert["category"],
        message=alert["message"],
        details=alert.get("details", ""),
        comment="Test override comment",
    )
    session.add(override)
    session.commit()

    # 3. Re-evaluate - alert should be filtered and score back to 100
    SecurityRuleEngine.invalidate(guild_id)
    evaluation_after = SecurityRuleEngine.evaluate(guild_id, session)
    assert len(evaluation_after["alerts"]) == 0
    assert evaluation_after["score"] == 100

    # 4. Re-evaluate with include_overridden=True
    evaluation_incl = SecurityRuleEngine.evaluate(guild_id, session, include_overridden=True)
    assert len(evaluation_incl["alerts"]) == 1
    assert evaluation_incl["alerts"][0]["alert_hash"] == alert_hash
    # Score should still be 100 since it is overridden
    assert evaluation_incl["score"] == 100

    # 5. Remove override
    session.delete(override)
    session.commit()

    # 6. Re-evaluate - alert should be active again
    SecurityRuleEngine.invalidate(guild_id)
    evaluation_final = SecurityRuleEngine.evaluate(guild_id, session)
    assert len(evaluation_final["alerts"]) == 1
    assert evaluation_final["score"] < 100
