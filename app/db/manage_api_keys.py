import argparse
import logging
import secrets
import sys
from pathlib import Path

# Ensure consistent imports
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.db.models import ApiKey

logging.basicConfig(level=logging.INFO, format="%(message)s")


def add_api_key(name: str, scopes: str, specific_key: str | None = None):
    engine = init_connection_engine()
    with Session(engine) as session:
        # Check if name exists
        existing = session.exec(select(ApiKey).where(ApiKey.name == name)).first()
        if existing:
            logging.error(f"API Key with name '{name}' already exists.")
            sys.exit(1)

        new_key = specific_key if specific_key else f"pc_{secrets.token_urlsafe(32)}"
        api_key = ApiKey(key=new_key, name=name, scopes=scopes, is_active=True)
        session.add(api_key)
        session.commit()
        logging.info("API Key created successfully.")
        logging.info(f"Name:   {name}")
        logging.info(f"Key:    {new_key}")
        logging.info(f"Scopes: {scopes}")


def revoke_api_key(key_id: int):
    engine = init_connection_engine()
    with Session(engine) as session:
        api_key = session.get(ApiKey, key_id)
        if not api_key:
            logging.error(f"API Key with ID {key_id} not found.")
            sys.exit(1)

        api_key.is_active = False
        session.add(api_key)
        session.commit()
        logging.info(f"API Key '{api_key.name}' (ID: {key_id}) has been revoked.")


def list_api_keys():
    engine = init_connection_engine()
    with Session(engine) as session:
        keys = session.exec(select(ApiKey)).all()
        if not keys:
            logging.info("No API Keys found.")
            return

        logging.info(f"{'ID':<5} | {'Name':<20} | {'Active':<8} | {'Scopes'}")
        logging.info("-" * 60)
        for k in keys:
            active = "Yes" if k.is_active else "No"
            logging.info(f"{k.id:<5} | {k.name:<20} | {active:<8} | {k.scopes}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage Powercord API Keys")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # ADD
    add_parser = subparsers.add_parser("add", help="Add a new API Key")
    add_parser.add_argument("name", type=str, help="Name or description for the API key")
    add_parser.add_argument(
        "--scopes",
        type=str,
        default='["global"]',
        help="JSON string list of scopes, e.g. '[\"global\"]' or '[\"example\"]'",
    )
    add_parser.add_argument(
        "--key",
        type=str,
        default=None,
        help="Specific exact key to insert (useful for migrating existing legacy keys). If omitted, a secure key is generated.",
    )

    # REVOKE
    revoke_parser = subparsers.add_parser("revoke", help="Revoke an existing API Key")
    revoke_parser.add_argument("id", type=int, help="ID of the API Key to revoke")

    # LIST
    list_parser = subparsers.add_parser("list", help="List all API Keys")

    args = parser.parse_args()

    if args.action == "add":
        add_api_key(args.name, args.scopes, args.key)
    elif args.action == "revoke":
        revoke_api_key(args.id)
    elif args.action == "list":
        list_api_keys()
