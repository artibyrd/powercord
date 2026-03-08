"""Remove a Dashboard Admin by Discord User ID."""

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


def remove_admin(user_id: int):
    """Remove a user from the Dashboard Admin list."""
    print(f"Removing Dashboard Admin: {user_id}")
    engine = init_connection_engine()
    with Session(engine) as session:
        existing = session.get(AdminUser, user_id)
        if not existing:
            print(f"User {user_id} is not an admin.")
            return

        session.delete(existing)
        session.commit()
    print(f"Successfully removed user {user_id} from Dashboard Admins.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove a Dashboard Admin.")
    parser.add_argument("user_id", type=int, help="The Discord User ID to remove.")

    args = parser.parse_args()
    remove_admin(args.user_id)
