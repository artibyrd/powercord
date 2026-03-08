import sys
from pathlib import Path

from sqlmodel import SQLModel

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.common.alchemy import init_connection_engine


def ensure_tables():
    print("Ensuring database tables exist...")
    engine = init_connection_engine()
    SQLModel.metadata.create_all(engine)
    print("Tables created/verified.")


if __name__ == "__main__":
    ensure_tables()
