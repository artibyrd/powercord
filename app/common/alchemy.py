import logging
import os
import sys
from pathlib import Path

import sqlalchemy
from sqlmodel import Session, create_engine, text

# Add the project root directory to the Python path to ensure consistent imports.
# This must be done before any local application imports.
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import app.common.gsm_loader as gsecrets

gsecrets.load_env()


# Module-level singleton engine to prevent connection pool exhaustion.
# Creating a new engine per call would spawn a new pool each time,
# quickly exceeding PostgreSQL's max_connections limit.
_engine = None


def init_connection_engine():
    """Returns a shared SQLAlchemy engine, creating it on first call."""
    global _engine
    if _engine is not None:
        return _engine
    logging.debug("Init database connection...")
    db_config = {
        "pool_size": 5,
        "max_overflow": 2,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    }
    _engine = init_tcp_connection_engine(db_config)
    return _engine


def get_database_url():
    """Constructs the database URL from environment variables."""
    db_host = os.environ.get("DB_HOST")
    if not db_host:
        logging.error("DB_HOST environment variable is missing or empty.")
        raise ValueError("DB_HOST environment variable is missing or empty.")

    host_args = db_host.split(":")
    if len(host_args) != 2:
        logging.error(f"Invalid DB_HOST format: {db_host}. Expected hostname:port")
        raise ValueError(f"Invalid DB_HOST format: {db_host}. Expected hostname:port")

    db_hostname, db_port = host_args[0], int(host_args[1])
    return sqlalchemy.engine.URL.create(
        drivername="postgresql+pg8000",
        username=os.environ.get("POSTGRES_USER"),
        password=os.environ.get("POSTGRES_PASSWORD"),
        host=db_hostname,
        port=db_port,
        database=os.environ.get("POSTGRES_DB"),
    )


def init_tcp_connection_engine(db_config):
    logging.debug("Connecting to localhost DB instance...")
    url = get_database_url()

    # Use SQLModel's create_engine
    engine = create_engine(url, **db_config)
    logging.debug("DB Connected!")
    return engine


def get_session():
    """Dependency to provide a database session."""
    engine = init_connection_engine()
    with Session(engine) as session:
        yield session


if __name__ == "__main__":
    db = init_connection_engine()
    print("Testing connection with SQLModel engine...")
    try:
        with db.connect() as conn:
            print(f"Connection successful: {db.url}")

        # Optional: Try a simple query
        from sqlalchemy import text

        with Session(db) as session:
            result = session.execute(text("SELECT 1")).one()  # raw text needs execute()
            print(f"Query result: {result}")

    except Exception as e:
        print(f"Error: {e}")
