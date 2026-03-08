import sys
from pathlib import Path

from sqlmodel import Session, text

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.common.alchemy import init_connection_engine


def reset_admins():
    print("Resetting Dashboard Admins...")
    engine = init_connection_engine()
    with Session(engine) as session:
        session.exec(text("DELETE FROM admin_users"))
        session.commit()
    print("All dashboard admins have been removed. The next user to log in will become an Admin.")


if __name__ == "__main__":
    reset_admins()
