import json
import os
import sys

# Ensure app is importable
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from sqlmodel import Session, SQLModel, create_engine, select
from app.db.models import DiscordChannel, DiscordRole, DiscordAuditorConfig
from app.extensions.utilities.widget import PublicAnnouncementProtection

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

with Session(engine) as session:
    session.execute(sqlalchemy.text("DELETE FROM discord_channels;"))
    session.execute(sqlalchemy.text("DELETE FROM discord_roles;"))
    session.execute(sqlalchemy.text("DELETE FROM discord_auditor_configs;"))
    session.commit()

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

    print("Checking DB:")
    print("Configs:", session.exec(select(DiscordAuditorConfig)).all())
    print("Roles:", session.exec(select(DiscordRole)).all())
    print("Channels:", session.exec(select(DiscordChannel)).all())

    rule = PublicAnnouncementProtection()
    alerts = rule.evaluate(guild_id, session)
    print("Alerts count:", len(alerts))
    for alert in alerts:
        print("  Alert:", alert["message"], "| Details:", alert["details"])
