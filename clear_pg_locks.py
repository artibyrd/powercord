import os

import sqlalchemy
from sqlalchemy import text
from sqlmodel import create_engine

os.environ["POWERCORD_DB_HOST"] = "localhost:5433"
os.environ["POWERCORD_POSTGRES_USER"] = "powercord"
os.environ["POWERCORD_POSTGRES_PASSWORD"] = "test_pass"  # noqa: S105

db_host = os.environ["POWERCORD_DB_HOST"]
host_parts = db_host.split(":")

maintenance_url = sqlalchemy.engine.URL.create(
    drivername="postgresql+pg8000",
    username=os.environ["POWERCORD_POSTGRES_USER"],
    password=os.environ["POWERCORD_POSTGRES_PASSWORD"],
    host=host_parts[0],
    port=int(host_parts[1]),
    database="postgres",
)

engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
with engine.connect() as conn:
    print("Terminating other backends...")
    result = conn.execute(
        text("""
        SELECT pg_terminate_backend(pid), query, state
        FROM pg_stat_activity
        WHERE (datname IN ('postgres', 'powercord_test')) AND pid <> pg_backend_pid();
    """)
    ).fetchall()
    print("Terminated backends:", result)
