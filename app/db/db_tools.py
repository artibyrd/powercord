import argparse
import logging
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

# Ensure consistent imports
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.common import gsm_loader
from app.common.alchemy import init_connection_engine
from app.db.models import ApiKey

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def get_or_create_internal_key() -> str:
    """
    Retrieves the internal API key from the database, generating a new secure
    key if it does not already exist. Handles concurrent startup race conditions.
    """
    engine = init_connection_engine()
    with Session(engine) as session:
        # Check if the key already exists
        statement = select(ApiKey).where(ApiKey.name == "system_internal")
        existing_key = session.exec(statement).first()
        if existing_key:
            return existing_key.key

        # Key does not exist, let's try to create one
        new_key_value = f"pc_internal_{secrets.token_urlsafe(32)}"
        new_key = ApiKey(key=new_key_value, name="system_internal", is_active=True, scopes='["global"]')
        session.add(new_key)
        try:
            session.commit()
            return new_key_value
        except IntegrityError:
            # Another process inserted the key at the exact same time
            session.rollback()
            existing_key = session.exec(select(ApiKey).where(ApiKey.name == "system_internal")).first()
            if existing_key:
                return existing_key.key
            raise RuntimeError("Failed to get or create internal API key due to unexpected database state.") from None


def _get_executable_path(executable_name: str) -> str:
    """Finds the path to a required executable, checking standard locations if not in PATH."""
    path = shutil.which(executable_name)
    if path:
        return path

    # Check common Windows PostgreSQL installation paths
    if sys.platform == "win32":
        base_path = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PostgreSQL"
        if base_path.exists():
            matches = list(base_path.glob(f"*/bin/{executable_name}.exe"))
            if matches:
                matches.sort(reverse=True)
                return str(matches[0])

            pgadmin_matches = list(base_path.glob(f"*/pgAdmin 4/runtime/{executable_name}.exe"))
            if pgadmin_matches:
                pgadmin_matches.sort(reverse=True)
                return str(pgadmin_matches[0])

    return executable_name


def _is_docker_running() -> bool:
    """Checks if the Powercord docker container is currently running."""
    try:
        # Check if any container with the name 'app' or project name is running
        result = subprocess.run(
            ["docker", "compose", "ps", "--services", "--filter", "status=running"],  # noqa: S603, S607
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return "app" in result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_db_credentials():
    """Returns database credentials from the environment."""
    gsm_loader.load_env()
    host_full = os.environ.get("POWERCORD_DB_HOST", "localhost:5432")
    host_parts = host_full.split(":")
    host = host_parts[0]
    port = host_parts[1] if len(host_parts) > 1 else "5432"

    return {
        "user": os.environ.get("POWERCORD_POSTGRES_USER", "postgres"),
        "password": os.environ.get("POWERCORD_POSTGRES_PASSWORD", "postgres"),
        "db": os.environ.get("POWERCORD_POSTGRES_DB", "postgres"),
        "host": host,
        "port": port,
    }


def export_database(output_file: str):
    """Exports the database to a SQL file."""
    creds = get_db_credentials()
    output_path = Path(output_file.strip("\"'")).resolve()

    # Ensure the parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if _is_docker_running():
            logging.info("Detected running Docker container. Exporting from container...")
            # We use docker compose exec and pipe the output to a local file
            cmd = [
                "docker",
                "compose",
                "exec",
                "-T",  # Disable pseudo-tty allocation to allow clean stdout piping
                "-e",
                f"PGPASSWORD={creds['password']}",
                "app",
                "pg_dump",
                "-U",
                creds["user"],
                "-h",
                creds["host"],
                "-p",
                creds["port"],
                "--clean",  # Include DROP statements
                "--if-exists",  # Don't error on DROP if missing
                "--no-owner",  # Skip ownership reassignment issues
                "-d",
                creds["db"],
            ]

            with open(output_path, "w", encoding="utf-8") as f:
                subprocess.run(cmd, cwd=str(project_root), stdout=f, check=True)  # noqa: S603, S607

        else:
            logging.info("Exporting from local host PostgreSQL instance...")
            env = os.environ.copy()
            env["PGPASSWORD"] = creds["password"]

            pg_dump_path = _get_executable_path("pg_dump")

            cmd = [
                pg_dump_path,
                "-U",
                creds["user"],
                "-h",
                creds["host"],
                "-p",
                creds["port"],
                "--clean",
                "--if-exists",
                "--no-owner",
                "-d",
                creds["db"],
                "-f",
                str(output_path),
            ]
            subprocess.run(cmd, env=env, check=True)  # noqa: S603

        logging.info(f"Successfully exported database to {output_path}")

    except FileNotFoundError as e:
        logging.error(f"Missing required executable. Please ensure PostgreSQL tools (pg_dump) are installed. {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to export database. Command exited with code {e.returncode}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)


def import_database(input_file: str):
    """Imports a SQL file into the database."""
    creds = get_db_credentials()
    input_path = Path(input_file.strip("\"'")).resolve()

    if not input_path.exists():
        logging.error(f"File not found: {input_path}")
        sys.exit(1)

    try:
        if _is_docker_running():
            logging.info("Detected running Docker container. Importing into container...")
            cmd = [
                "docker",
                "compose",
                "exec",
                "-T",
                "-e",
                f"PGPASSWORD={creds['password']}",
                "app",
                "psql",
                "-U",
                creds["user"],
                "-h",
                creds["host"],
                "-p",
                creds["port"],
                "-d",
                creds["db"],
            ]

            with open(input_path, "r", encoding="utf-8") as f:
                subprocess.run(cmd, cwd=str(project_root), stdin=f, check=True)  # noqa: S603, S607

        else:
            logging.info("Importing into local host PostgreSQL instance...")
            env = os.environ.copy()
            env["PGPASSWORD"] = creds["password"]

            psql_path = _get_executable_path("psql")

            cmd = [
                psql_path,
                "-U",
                creds["user"],
                "-h",
                creds["host"],
                "-p",
                creds["port"],
                "-d",
                creds["db"],
                "-f",
                str(input_path),
            ]
            subprocess.run(cmd, env=env, check=True)  # noqa: S603

        logging.info(f"Successfully imported database from {input_path}")

    except FileNotFoundError as e:
        logging.error(f"Missing required executable. Please ensure PostgreSQL tools (psql) are installed. {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to import database. Command exited with code {e.returncode}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Powercord Database Export/Import Tool")
    parser.add_argument("action", choices=["export", "import"], help="Action to perform (export or import)")
    parser.add_argument("file", type=str, help="Path to the SQL file")

    args = parser.parse_args()

    if args.action == "export":
        export_database(args.file)
    elif args.action == "import":
        import_database(args.file)
