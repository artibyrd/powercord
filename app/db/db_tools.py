import argparse
import datetime
import gzip
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


def export_database(output_file: str, is_migration: bool = False):
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
                "localhost",
                "-p",
                "5432",
            ]

            if is_migration:
                # For migration, we typically want data-only with inserts to avoid schema conflicts
                # in a destination that has already been provisioned with Alembic.
                cmd.extend(["--data-only", "--inserts", "--no-owner"])
            else:
                # Standard full backup
                cmd.extend(["--clean", "--if-exists", "--no-owner"])

            cmd.extend(["-d", creds["db"]])

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
            ]

            if is_migration:
                cmd.extend(["--data-only", "--inserts", "--no-owner"])
            else:
                cmd.extend(["--clean", "--if-exists", "--no-owner"])

            cmd.extend(["-d", creds["db"], "-f", str(output_path)])
            subprocess.run(cmd, env=env, check=True)  # noqa: S603

        logging.info(f"Successfully exported database to {output_path}")

    except FileNotFoundError as e:
        logging.error(f"Missing required executable. Please ensure PostgreSQL tools (pg_dump) are installed. {e}")
        raise RuntimeError("Missing pg_dump executable") from e
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to export database. Command exited with code {e.returncode}")
        raise RuntimeError("pg_dump command failed") from e
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        raise RuntimeError("Unexpected error during export") from e


class BackupService:
    BACKUP_DIR = Path("/var/lib/postgresql/data/backups")
    RETENTION_DAYS = 7

    @classmethod
    def create_daily_backup(cls):
        """Creates a database backup with the current date."""
        # Use local dir if not in docker
        if not _is_docker_running():
            cls.BACKUP_DIR = project_root / "backups"

        cls.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        backup_file = cls.BACKUP_DIR / f"powercord_db_backup_{date_str}.sql"
        gz_backup_file = cls.BACKUP_DIR / f"powercord_db_backup_{date_str}.sql.gz"

        logging.info(f"Starting daily database backup to {gz_backup_file}")
        try:
            export_database(str(backup_file))
            with open(backup_file, "rb") as f_in:
                with gzip.open(gz_backup_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            backup_file.unlink()
            logging.info("Daily database backup completed successfully.")
            cls.prune_old_backups()
        except Exception as e:
            logging.error(f"Daily database backup failed: {e}")

    @classmethod
    def prune_old_backups(cls):
        """Removes backups older than RETENTION_DAYS."""
        logging.info(f"Pruning database backups older than {cls.RETENTION_DAYS} days in {cls.BACKUP_DIR}")
        if not cls.BACKUP_DIR.exists():
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        retention_td = datetime.timedelta(days=cls.RETENTION_DAYS)

        for file in cls.BACKUP_DIR.glob("powercord_db_backup_*.sql.gz"):
            try:
                # Get file modification time
                mtime = datetime.datetime.fromtimestamp(file.stat().st_mtime, tz=datetime.timezone.utc)
                if now - mtime > retention_td:
                    logging.info(f"Removing old backup file: {file.name}")
                    file.unlink()
            except Exception as e:
                logging.error(f"Failed to process old backup {file.name}: {e}")

    scheduler = None

    @classmethod
    def start_scheduler(cls):
        """Starts the APScheduler for daily backups."""
        if cls.scheduler is not None:
            return

        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        cls.scheduler = AsyncIOScheduler()
        # Schedule to run every day at 03:00 UTC
        cls.scheduler.add_job(cls.create_daily_backup, trigger="cron", hour=3, minute=0, id="daily_database_backup")
        cls.scheduler.start()
        logging.info("APScheduler started: Daily database backup scheduled for 03:00 UTC.")

    @classmethod
    def stop_scheduler(cls):
        """Stops the APScheduler."""
        if cls.scheduler:
            cls.scheduler.shutdown()
            cls.scheduler = None
            logging.info("APScheduler stopped.")


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
                "localhost",
                "-p",
                "5432",
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
        raise RuntimeError("Missing psql executable") from e
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to import database. Command exited with code {e.returncode}")
        raise RuntimeError("psql command failed") from e
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        raise RuntimeError("Unexpected error during import") from e


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Powercord Database Export/Import/Backup Tool")
    parser.add_argument(
        "action", choices=["export", "import", "backup"], help="Action to perform (export, import, or backup)"
    )
    parser.add_argument("file", type=str, nargs="?", help="Path to the SQL file (required for export/import)")
    parser.add_argument("--migration", action="store_true", help="Use migration format (data-only inserts)")

    args = parser.parse_args()

    try:
        if args.action == "export":
            if not args.file:
                parser.error("The 'export' action requires a file path.")
            export_database(args.file, is_migration=args.migration)
        elif args.action == "import":
            if not args.file:
                parser.error("The 'import' action requires a file path.")
            import_database(args.file)
        elif args.action == "backup":
            BackupService.create_daily_backup()
    except Exception:
        sys.exit(1)
