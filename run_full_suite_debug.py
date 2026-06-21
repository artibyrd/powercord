import json
import os
import sys

# Ensure app is importable
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from sqlmodel import Session, SQLModel, create_engine, select
from app.db.models import DiscordChannel, DiscordRole
from app.extensions.utilities.widget import CategoryPermissionBaseline, SecurityRuleEngine

os.environ["POWERCORD_DB_HOST"] = "localhost:5433"
os.environ["POWERCORD_POSTGRES_USER"] = "powercord"
os.environ["POWERCORD_POSTGRES_PASSWORD"] = "OBPwDbD7zUFZw2YhL4h6zyR"
os.environ["POWERCORD_POSTGRES_DB"] = "powercord_test"

from app.common.testing import TEST_DB_NAME
import sqlalchemy

DATABASE_URL = sqlalchemy.engine.URL.create(
    drivername="postgresql+pg8000",
    username=os.environ["POWERCORD_POSTGRES_USER"],
    password=os.environ["POWERCORD_POSTGRES_PASSWORD"],
    host="localhost",
    port=5433,
    database=TEST_DB_NAME,
)

engine = create_engine(DATABASE_URL)
SQLModel.metadata.create_all(engine)

# Run a sequence of tests using a session
with Session(engine) as session:
    # Clean DB
    session.execute(sqlalchemy.text("DELETE FROM discord_channels;"))
    session.execute(sqlalchemy.text("DELETE FROM discord_roles;"))
    session.commit()

    print("--- Running test_security_rule_engine_evaluate_caching simulation ---")
    # Simulate test_security_rule_engine_evaluate_caching
    # Seed DB
    from app.db.models import DiscordAuditorConfig
    config = DiscordAuditorConfig(guild_id=12345, staff_separator_role_id=900)
    sep_role = DiscordRole(id=900, guild_id=12345, name="--- Staff ---", permissions=0, position=5)
    session.add_all([config, sep_role])
    session.commit()

    # Clear cache before starting
    SecurityRuleEngine._evaluation_cache.clear()
    res1 = SecurityRuleEngine.evaluate(12345, session)
    print("Cache size:", len(SecurityRuleEngine._evaluation_cache))

    print("--- Cleaning DB for next test ---")
    session.execute(sqlalchemy.text("DELETE FROM discord_channels;"))
    session.execute(sqlalchemy.text("DELETE FROM discord_roles;"))
    session.execute(sqlalchemy.text("DELETE FROM discord_auditor_configs;"))
    session.commit()

    print("--- Running test_category_baseline_active_leak_not_annotated simulation ---")
    guild_id = 12345
    parent = DiscordChannel(
        id=100,
        guild_id=guild_id,
        parent_id=None,
        name="Category",
        type="category",
        overwrites=json.dumps({"999": {"allow": 0, "deny": 0}}),
    )
    child = DiscordChannel(
        id=101,
        guild_id=guild_id,
        parent_id=100,
        name="open-channel",
        type="text",
        overwrites=json.dumps({"999": {"allow": 1 << 11, "deny": 0}}),
    )
    session.add_all([parent, child])
    session.commit()

    print("Channels in DB:")
    chans = session.exec(select(DiscordChannel)).all()
    for ch in chans:
        print(f"  ID={ch.id}, Name={ch.name}, Type={ch.type}, parent_id={ch.parent_id}")

    # Now evaluate via SecurityRuleEngine
    print("Evaluating via SecurityRuleEngine.evaluate...")
    res = SecurityRuleEngine.evaluate(guild_id, session)
    print("SecurityRuleEngine Score:", res["score"])
    print("SecurityRuleEngine Alerts count:", len(res["alerts"]))
    for alert in res["alerts"]:
        print(f"  Alert: {alert['rule']}, Details: {alert['details']}")
