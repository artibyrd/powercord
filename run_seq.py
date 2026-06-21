import json
import os
import sys

# Ensure app is importable
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from sqlmodel import Session, SQLModel, create_engine, select
from app.db.models import DiscordChannel, DiscordRole, DiscordAuditorConfig
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

# Let's list the test names we want to simulate
# We'll simulate all 22 tests in order!

def clean_db(session):
    from sqlalchemy import text
    session.execute(text("DELETE FROM discord_channels;"))
    session.execute(text("DELETE FROM discord_roles;"))
    session.execute(text("DELETE FROM discord_auditor_configs;"))
    session.execute(text("DELETE FROM guild_extension_settings;"))
    session.execute(text("DELETE FROM site_settings;"))
    session.execute(text("DELETE FROM user_settings;"))
    session.commit()

# We will run them in one big sequence of clean -> execute -> clean
tests = []

def test_1(session):
    # test_category_permission_baseline
    guild_id = 12345
    parent = DiscordChannel(id=100, guild_id=guild_id, parent_id=None, name="Category", type="category", overwrites=json.dumps({"999": {"allow": 0, "deny": 1 << 10}}))
    child_exposed = DiscordChannel(id=101, guild_id=guild_id, parent_id=100, name="exposed-channel", type="text", overwrites=json.dumps({"999": {"allow": 1 << 10, "deny": 0}}))
    child_secure = DiscordChannel(id=102, guild_id=guild_id, parent_id=100, name="secure-channel", type="text", overwrites=json.dumps({"999": {"allow": 0, "deny": 1 << 10}}))
    session.add_all([parent, child_exposed, child_secure])
    session.commit()
    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)
    print("Test 1 alerts count:", len(alerts))

def test_20(session):
    # test_security_rule_engine_evaluate_caching
    guild_id = 12345
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=900)
    sep_role = DiscordRole(id=900, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    session.add_all([config, sep_role])
    session.commit()
    SecurityRuleEngine._evaluation_cache.clear()
    res1 = SecurityRuleEngine.evaluate(guild_id, session)
    res2 = SecurityRuleEngine.evaluate(guild_id, session)
    SecurityRuleEngine.invalidate(guild_id)
    res3 = SecurityRuleEngine.evaluate(guild_id, session)
    print("Test 20 evaluated cache size:", len(SecurityRuleEngine._evaluation_cache))

def test_21(session):
    # test_category_baseline_inert_leak_annotation
    guild_id = 12345
    parent = DiscordChannel(id=100, guild_id=guild_id, parent_id=None, name="Category", type="category", overwrites=json.dumps({"999": {"allow": 0, "deny": 1 << 10}}))
    child = DiscordChannel(id=101, guild_id=guild_id, parent_id=100, name="restricted-channel", type="text", overwrites=json.dumps({"999": {"allow": 1 << 11, "deny": 1 << 10}}))
    session.add_all([parent, child])
    session.commit()
    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)
    print("Test 21 alerts count:", len(alerts))

def test_22(session):
    # test_category_baseline_active_leak_not_annotated
    guild_id = 12345
    parent = DiscordChannel(id=100, guild_id=guild_id, parent_id=None, name="Category", type="category", overwrites=json.dumps({"999": {"allow": 0, "deny": 0}}))
    child = DiscordChannel(id=101, guild_id=guild_id, parent_id=100, name="open-channel", type="text", overwrites=json.dumps({"999": {"allow": 1 << 11, "deny": 0}}))
    session.add_all([parent, child])
    session.commit()
    rule = CategoryPermissionBaseline()
    alerts = rule.evaluate(guild_id, session)
    print("Test 22 alerts count:", len(alerts))

# Execute them
all_sims = [test_1, test_20, test_21, test_22]
for sim in all_sims:
    with Session(engine) as session:
        clean_db(session)
        sim(session)
        clean_db(session)
