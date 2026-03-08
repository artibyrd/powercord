import argparse
import sys
from pathlib import Path

from sqlmodel import Session

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.common.alchemy import init_connection_engine
from app.db.models import AdminUser


def add_admin(user_id: int, comment: str = "Added via CLI"):
    print(f"Adding Dashboard Admin: {user_id} ({comment})")
    engine = init_connection_engine()
    with Session(engine) as session:
        existing = session.get(AdminUser, user_id)
        if existing:
            print(f"User {user_id} is already an admin.")
            return

        admin = AdminUser(user_id=user_id, comment=comment)
        session.add(admin)
        session.commit()
    print(f"Successfully added user {user_id} as a Dashboard Admin.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a Dashboard Admin.")
    parser.add_argument("user_id", type=int, help="The Discord User ID of the new admin.")
    parser.add_argument("--comment", type=str, nargs="+", default=["Added", "via", "CLI"], help="Optional comment.")

    args = parser.parse_args()
    comment = " ".join(args.comment)
    add_admin(args.user_id, comment)
