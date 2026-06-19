import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlmodel import Session, SQLModel  # noqa: E402

from app.common.alchemy import init_connection_engine  # noqa: E402
from app.ui.helpers import seed_global_settings_if_empty  # noqa: E402


def ensure_tables():
    print("Ensuring database tables exist...")
    engine = init_connection_engine()
    SQLModel.metadata.create_all(engine)
    print("Tables created/verified.")

    with Session(engine) as session:
        seed_global_settings_if_empty(session)


if __name__ == "__main__":
    ensure_tables()
