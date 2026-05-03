import os
import sys
import types
from importlib.machinery import ModuleSpec, SourceFileLoader

# The canonical test database name — tests MUST never write to the dev database.
TEST_DB_NAME = "powercord_test"


def ensure_test_database() -> None:
    """Create the dedicated test database and enable required extensions.

    Connects to the PostgreSQL server's maintenance database (``postgres``)
    and creates ``powercord_test`` if it doesn't exist.  This function also
    enables ``pg_trgm`` in the test database so that trigram-based search
    queries work identically to production.

    This should be called **once per test session** from a session-scoped
    fixture in ``conftest.py``.  It is safe to call multiple times — the
    ``CREATE DATABASE`` and ``CREATE EXTENSION`` statements use ``IF NOT
    EXISTS`` guards.

    Environment variables consumed (must be set before calling):
        ``POWERCORD_DB_HOST``
        ``POWERCORD_POSTGRES_USER``
        ``POWERCORD_POSTGRES_PASSWORD``
    """
    import sqlalchemy
    from sqlalchemy import text
    from sqlmodel import create_engine

    db_host = os.environ["POWERCORD_DB_HOST"]
    host_parts = db_host.split(":")

    # 1. Connect to the maintenance DB to create the test database.
    maintenance_url = sqlalchemy.engine.URL.create(
        drivername="postgresql+pg8000",
        username=os.environ["POWERCORD_POSTGRES_USER"],
        password=os.environ["POWERCORD_POSTGRES_PASSWORD"],
        host=host_parts[0],
        port=int(host_parts[1]),
        database="postgres",
    )
    maint_engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    with maint_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": TEST_DB_NAME},
        ).fetchone()
        if not exists:
            # CREATE DATABASE cannot be parameterized — the name is a
            # compile-time constant (TEST_DB_NAME) so this is safe.
            conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))  # noqa: S608
    maint_engine.dispose()

    # 2. Connect to the test database and enable pg_trgm.
    test_url = sqlalchemy.engine.URL.create(
        drivername="postgresql+pg8000",
        username=os.environ["POWERCORD_POSTGRES_USER"],
        password=os.environ["POWERCORD_POSTGRES_PASSWORD"],
        host=host_parts[0],
        port=int(host_parts[1]),
        database=TEST_DB_NAME,
    )
    test_engine = create_engine(test_url, isolation_level="AUTOCOMMIT")
    with test_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    test_engine.dispose()


def setup_extension_test_env(extension_name: str, conftest_file_path: str):
    """
    Sets up the test environment for a disconnected extension repository.
    This registers the extension into sys.modules natively so that tests and relative imports
    inside the extension can seamlessly map the namespace without structural errors.

    Args:
        extension_name: The name of the extension (e.g. 'honeypot', 'midi_library').
        conftest_file_path: The __file__ path of the local conftest.py calling this.
    """
    import app.extensions

    # Create the top-level namespace module
    ext_mod = types.ModuleType(extension_name)
    ext_mod.__package__ = f"app.extensions.{extension_name}"

    # We resolve the root directory of the extension relative to its tests/conftest.py
    root_dir = os.path.abspath(os.path.join(os.path.dirname(conftest_file_path), ".."))
    ext_mod.__path__ = [root_dir]

    # Register it into sys.modules and the app.extensions parent namespace
    sys.modules[f"app.extensions.{extension_name}"] = ext_mod
    setattr(app.extensions, extension_name, ext_mod)

    # Instead of standard __import__, evaluate the actual files directly
    # so we populate sys.modules and make relative imports from test files work.
    for file in os.listdir(root_dir):
        if file.endswith(".py") and not file.startswith("__") and file != "test.py":
            mod_name = file[:-3]
            full_name = f"app.extensions.{extension_name}.{mod_name}"

            # This loader injects `from app.extensions.<ext_name> import <file>`
            loader = SourceFileLoader(full_name, os.path.join(root_dir, file))
            spec = ModuleSpec(name=full_name, loader=loader)

            # We push the spec so relative imports inside it know their parent package
            mod = types.ModuleType(spec.name)
            mod.__file__ = loader.path
            mod.__package__ = f"app.extensions.{extension_name}"
            mod.__loader__ = loader
            mod.__spec__ = spec

            sys.modules[full_name] = mod
            setattr(ext_mod, mod_name, mod)

            loader.exec_module(mod)
