import json
import os
import sys

# Ensure app is importable
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from sqlmodel import Session, SQLModel, create_engine, select
from app.db.models import DiscordChannel
from app.extensions.utilities.widget import CategoryPermissionBaseline

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

print(f"Connecting to: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)
SQLModel.metadata.create_all(engine)

try:
    with Session(engine) as session:
        # Clean table
        from sqlalchemy import text
        session.execute(text("DELETE FROM discord_channels;"))
        session.commit()

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

        session.add(parent)
        session.add(child)
        session.commit()
        print("Commited successfully.")

        print("Querying channels...")
        chans = session.exec(select(DiscordChannel)).all()
        print(f"Found {len(chans)} channels:")
        for ch in chans:
            print(f"ID={ch.id}, Name={ch.name}, Type={ch.type}, parent_id={ch.parent_id}, overwrites={ch.overwrites}")

        rule = CategoryPermissionBaseline()
        alerts = rule.evaluate(guild_id, session)
        print("Alerts:")
        print(alerts)
except Exception as e:
    import traceback
    traceback.print_exc()
