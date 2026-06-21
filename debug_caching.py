import os
import json
os.environ["POWERCORD_DB_HOST"] = "localhost:5433"
os.environ["POWERCORD_POSTGRES_USER"] = "powercord"
os.environ["POWERCORD_POSTGRES_PASSWORD"] = "test_pass"
os.environ["POWERCORD_DISCORD_TOKEN"] = "dummy_token"
os.environ["POWERCORD_SESSION_KEY"] = "dummy_session"
os.environ["POWERCORD_POSTGRES_DB"] = "powercord_test"

from sqlmodel import Session, create_engine, select
import sqlalchemy.engine
from app.db.models import DiscordAuditorConfig, DiscordRole
from app.extensions.utilities.widget import SecurityRuleEngine

DATABASE_URL = sqlalchemy.engine.URL.create(
    drivername="postgresql+pg8000",
    username="powercord",
    password="OBPwDbD7zUFZw2YhL4h6zyR",
    host="localhost",
    port=5433,
    database="powercord_test",
)

engine = create_engine(DATABASE_URL)
guild_id = 91000

with Session(engine) as session:
    # Clean previous
    from sqlmodel import text
    session.execute(text("TRUNCATE TABLE discord_roles CASCADE"))
    session.execute(text("TRUNCATE TABLE discord_auditor_configs CASCADE"))
    session.commit()

    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=91001)
    sep_role = DiscordRole(id=91001, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    session.add_all([config, sep_role])
    session.commit()

    print("Evaluating initial...")
    res1 = SecurityRuleEngine.evaluate(guild_id, session)
    print("res1 score:", res1["score"])
    print("res1 alerts:", json.dumps(res1["alerts"], indent=2))

    low_role = DiscordRole(id=91002, guild_id=guild_id, name="Low Admin", permissions=1 << 3, position=2)
    session.add(low_role)
    session.commit()

    print("\nEvaluating cached (should be same)...")
    res2 = SecurityRuleEngine.evaluate(guild_id, session)
    print("res2 score:", res2["score"])

    print("\nInvalidating...")
    SecurityRuleEngine.invalidate(guild_id)

    print("\nEvaluating fresh...")
    res3 = SecurityRuleEngine.evaluate(guild_id, session)
    print("res3 score:", res3["score"])
    print("res3 alerts:", json.dumps(res3["alerts"], indent=2))
