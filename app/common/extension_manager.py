"""Powercord Extension Manager — install, uninstall, and list extensions.

Provides a CLI interface (invoked via ``python -m app.common.extension_manager``)
and importable helpers for managing the extension lifecycle.  Each extension is
expected to ship a ``pyproject.toml`` or ``extension.json`` manifest (see schema in README).

Usage::

    # Install an extension from a local directory
    python -m app.common.extension_manager install /path/to/extension

    # Uninstall an extension by name
    python -m app.common.extension_manager uninstall honeypot

    # List all installed extensions
    python -m app.common.extension_manager list
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.common.extension_alembic import _update_alembic_ini as _alembic_update_ini
from app.common.extension_manifest import (
    _normalize_pkg_name,
    load_manifest,
)
from app.common.extension_manifest import (
    get_installed_extensions as _manifest_get_installed_extensions,
)

logger = logging.getLogger(__name__)

# Resolve the full path to the poetry executable once at import time.
# On Windows, `poetry` is often a `.cmd` wrapper that Python's subprocess
# cannot find without shell resolution — shutil.which handles this.
_POETRY_CMD = shutil.which("poetry") or "poetry"

# Resolve the canonical extensions directory relative to this file.
EXTENSIONS_DIR = Path(__file__).resolve().parents[1] / "extensions"

# Resolve the tests/extensions directory for extension test files.
# Tests are placed here so they share the framework's conftest fixtures.
TESTS_DIR = Path(__file__).resolve().parents[2] / "tests" / "extensions"


def _update_alembic_ini() -> None:
    """Dynamically reconstructs version_locations in alembic.ini based on active extensions."""
    _alembic_update_ini(EXTENSIONS_DIR)


def get_installed_extensions(extensions_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return a list of manifest dicts for every installed extension."""
    return _manifest_get_installed_extensions(extensions_dir or EXTENSIONS_DIR)


def _is_core_repository(repo_root: Path) -> bool:
    """Return True if repo_root is the core upstream framework repository."""
    if os.getenv("POWERCORD_ALLOW_CORE_EXT_INSTALL"):
        return False
    if (repo_root / ".downstream").exists() or (repo_root / ".powercord-downstream").exists():
        return False
    if repo_root.name == "powercord-downstream-server":
        return False
    try:
        git_cmd = shutil.which("git") or "git"
        res = subprocess.run(  # noqa: S603
            [git_cmd, "remote", "get-url", "--push", "origin"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.stdout.strip() == "DISABLED":
            return False
    except Exception:  # noqa: S110
        pass
    return repo_root.name == "powercord"


# ── Install ───────────────────────────────────────────────────────────


def install_extension(source_path: str | Path, *, allow_core: bool = False) -> None:
    """Install an extension from *source_path* into the extensions directory.

    Steps:
    1. Read and validate the manifest.
    2. Copy extension files into ``app/extensions/<name>/``.
    3. Install any declared Python dependencies via ``poetry add``.
    4. Run ``alembic upgrade head`` if the extension declares migrations.
    5. Fire the ``on_install`` lifecycle hook if one is registered.
    """
    if not allow_core and _is_core_repository(EXTENSIONS_DIR.parents[1]):
        print(
            "Error: Direct extension installation into the core 'powercord' repository is forbidden "
            "(inv-source-isolation-no-ad-hoc-cp).\n"
            "Install extensions strictly in 'powercord-downstream-server/' via:\n"
            f"  cd ../powercord-downstream-server && just ext-install {source_path}"
        )
        sys.exit(1)

    source = Path(source_path).resolve()
    if not source.is_dir():
        print(f"Error: Source path '{source}' is not a directory.")
        sys.exit(1)

    manifest = load_manifest(source)
    name = manifest["name"]
    dest = EXTENSIONS_DIR / name

    if source.resolve() == dest.resolve():
        print(f"Error: Cannot install extension '{name}' from its own installation directory.")
        sys.exit(1)

    # Guard against overwriting an existing installation unless we are reinstalling
    is_reinstall = False
    old_deps = []
    old_migration_version = None

    if dest.exists():
        print(f"Extension '{name}' is already installed at {dest}. Reinstalling...")
        is_reinstall = True
        try:
            old_manifest = load_manifest(dest)
            old_deps = old_manifest.get("python_dependencies", [])
            old_migration_version = old_manifest.get("latest_migration_version", None)
        except (FileNotFoundError, ValueError):
            pass

        # Clear out the existing files safely
        if dest.is_symlink() or (hasattr(dest, "is_junction") and dest.is_junction()):
            dest.unlink()
        else:
            shutil.rmtree(dest)

        test_dest = TESTS_DIR / name
        if test_dest.exists():
            if test_dest.is_symlink() or (hasattr(test_dest, "is_junction") and test_dest.is_junction()):
                test_dest.unlink()
            else:
                shutil.rmtree(test_dest)

    print(f"Installing extension '{name}' v{manifest['version']}...")

    # 1. Copy extension files (excluding tests — those go to tests/extensions/)
    shutil.copytree(
        source,
        dest,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            ".git",
            ".pytest_cache",
            "*.pyc",
            ".mypy_cache",
            "tests",
        ),
    )
    print(f"  ✅ Copied files to {dest}")

    # 1b. Copy extension tests into the framework's test directory
    source_tests = source / "tests"
    if source_tests.is_dir():
        test_dest = TESTS_DIR / name
        shutil.copytree(
            source_tests,
            test_dest,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                ".pytest_cache",
                "*.pyc",
                "conftest.py",
            ),
        )
        print(f"  ✅ Copied tests to {test_dest}")

    # 2. Install Python dependencies
    deps = manifest.get("python_dependencies", [])
    if deps:
        # Check if they are actually present in the root pyproject.toml
        root_pyproject = EXTENSIONS_DIR.parents[1] / "pyproject.toml"
        has_all_deps = False
        if root_pyproject.is_file():
            try:
                import tomllib

                with open(root_pyproject, "rb") as fh:
                    root_doc = tomllib.load(fh)
                root_deps = root_doc.get("tool", {}).get("poetry", {}).get("dependencies", {})
                has_all_deps = all(_normalize_pkg_name(dep) in root_deps for dep in deps)
            except Exception:  # noqa: S110
                pass

        if is_reinstall and set(deps) == set(old_deps) and has_all_deps:
            print("  📦 Skipped Python dependencies installation (no changes detected).")
        else:
            print(f"  📦 Installing {len(deps)} Python dependencies...")
            try:
                subprocess.run(  # noqa: S603
                    [_POETRY_CMD, "add", *deps],  # noqa: S607
                    check=True,
                    cwd=str(EXTENSIONS_DIR.parents[1]),
                )
                print("  ✅ Dependencies installed.")
            except subprocess.CalledProcessError as exc:
                print(f"  ⚠️  Failed to install dependencies: {exc}")
                print("     You may need to run 'poetry add' manually.")

    # 3. Run database migrations if needed
    if manifest.get("has_migrations", False):
        new_migration_version = manifest.get("latest_migration_version", None)

        # Skip if we are reinstalling and the migration version hasn't changed, provided it is explicitly set
        if is_reinstall and new_migration_version and new_migration_version == old_migration_version:
            print(f"  🗄️  Skipped database migrations (latest_migration_version '{new_migration_version}' unchanged).")
        else:
            print("  🗄️  Running database migrations...")
            target_rev = new_migration_version if new_migration_version else "head"
            _update_alembic_ini()
            try:
                subprocess.run(  # noqa: S603
                    [_POETRY_CMD, "run", "alembic", "upgrade", target_rev],  # noqa: S607
                    check=True,
                    cwd=str(EXTENSIONS_DIR.parents[1]),
                )
                print("  ✅ Migrations applied.")
            except subprocess.CalledProcessError as exc:
                print(f"  ⚠️  Migration failed: {exc}")
                print("     Run 'just db-upgrade' manually after resolving.")

    # 4. Fire on_install hook (if extension registers one)
    _fire_hook(name, "on_install")

    # 5. Report Discord permissions
    perms = manifest.get("discord_permissions", [])
    if perms:
        print(f"  🔑 Required Discord permissions: {', '.join(perms)}")
        print("     Ensure your bot has these permissions in each server.")

    print(f"\n✅ Extension '{name}' installed successfully!")
    print("   A new Docker build and deploy is required for production use.")


# ── Uninstall ─────────────────────────────────────────────────────────


def uninstall_extension(name: str) -> None:
    """Uninstall an extension by *name*.

    Steps:
    1. Fire the ``on_uninstall`` lifecycle hook if registered.
    2. Remove extension directory from ``app/extensions/<name>/``.
    3. Remove declared Python dependencies (if no other extension uses them).
    4. Warn about orphaned database tables.
    """
    dest = EXTENSIONS_DIR / name
    if not dest.exists():
        print(f"Error: Extension '{name}' is not installed.")
        sys.exit(1)

    # Load manifest for metadata
    try:
        manifest = load_manifest(dest)
    except (FileNotFoundError, ValueError):
        manifest = {"name": name, "python_dependencies": [], "has_migrations": False}

    # Check if internal extension
    if manifest.get("internal", False):
        print(f"⚠️  '{name}' is a built-in extension.  Removing it will delete framework files.")
        response = input("Are you sure you want to continue? [y/N] ").strip().lower()
        if response != "y":
            print("Cancelled.")
            return

    print(f"Uninstalling extension '{name}'...")

    # 1. Fire on_uninstall hook
    _fire_hook(name, "on_uninstall")

    # 2. Remove Python dependencies (only those unique to this extension).
    #    Each dep is removed individually so a locked transitive dependency
    #    (e.g. a .pyd file held by a running server) doesn't block removal
    #    of the other unrelated packages.
    deps_raw = manifest.get("python_dependencies", [])
    deps: list[str] = [str(d) for d in deps_raw] if isinstance(deps_raw, list) else []
    failed_deps: list[str] = []
    if deps:
        # Collect deps used by OTHER installed extensions so we don't remove shared ones
        other_deps: set[str] = set()
        for ext in get_installed_extensions():
            if ext["name"] != name:
                for dep in ext.get("python_dependencies", []):
                    # Normalize to just the package name (strip version specifiers)
                    other_deps.add(_normalize_pkg_name(dep))

        unique_deps = []
        for dep in deps:
            pkg_name = _normalize_pkg_name(dep)
            if pkg_name not in other_deps:
                unique_deps.append(pkg_name)

        if unique_deps:
            print(f"  📦 Removing {len(unique_deps)} unique dependencies...")
            for pkg in unique_deps:
                try:
                    subprocess.run(  # noqa: S603
                        [_POETRY_CMD, "remove", pkg],  # noqa: S607
                        check=True,
                        cwd=str(EXTENSIONS_DIR.parents[1]),
                    )
                    print(f"  ✅ Removed {pkg}")
                except subprocess.CalledProcessError:
                    failed_deps.append(pkg)
                    print(f"  ⚠️  Failed to remove {pkg} (file may be locked)")

            if failed_deps:
                print(f"\n  ⚠️  {len(failed_deps)} of {len(unique_deps)} dependencies could not be removed:")
                for pkg in failed_deps:
                    print(f"       - {pkg}")
                print("     Stop the server, then run manually:")
                print(f"       poetry remove {' '.join(failed_deps)}")

    # 3. Remove extension directory
    shutil.rmtree(dest)
    print(f"  ✅ Removed {dest}")
    _update_alembic_ini()

    # 3b. Remove extension tests from the framework test directory
    test_dest = TESTS_DIR / name
    if test_dest.exists():
        shutil.rmtree(test_dest)
        print(f"  ✅ Removed tests from {test_dest}")

    # 4. Warn about orphaned database tables and clean up alembic_version
    if manifest.get("has_migrations", False):
        print(f"  ⚠️  Extension '{name}' had database tables.")
        print("     These tables still exist in your database.")
        print("     To fully clean up, manually drop the tables or create a down-migration.")
        old_migration_version = manifest.get("latest_migration_version", None)
        if old_migration_version:
            try:
                from sqlalchemy import text

                from app.common.alchemy import init_connection_engine

                engine = init_connection_engine()
                with engine.begin() as conn:
                    conn.execute(
                        text("DELETE FROM alembic_version WHERE version_num = :version"),
                        {"version": old_migration_version},
                    )
                print(f"  ✅ Cleared revision {old_migration_version} from database history.")
            except Exception as e:
                print(f"  ⚠️  Failed to clear revision history: {e}")

    if failed_deps:
        print(f"\n⚠️  Extension '{name}' uninstalled with warnings (some deps remain).")
    else:
        print(f"\n✅ Extension '{name}' uninstalled successfully!")
    print("   A new Docker build and deploy is required for production use.")


# ── List ──────────────────────────────────────────────────────────────


def list_extensions() -> None:
    """Print a formatted table of all installed extensions."""
    extensions = get_installed_extensions()

    if not extensions:
        print("No extensions installed.")
        return

    # Header
    print(f"\n{'Name':<20} {'Version':<10} {'Type':<10} {'Description'}")
    print("─" * 80)

    for ext in extensions:
        ext_type = "internal" if ext.get("internal", False) else "external"
        desc = ext.get("description", "")
        if len(desc) > 40:
            desc = desc[:37] + "..."
        print(f"{ext['name']:<20} {ext.get('version', '?'):<10} {ext_type:<10} {desc}")

    print()


# ── Hook helper ───────────────────────────────────────────────────────


def _fire_hook(extension_name: str, event: str) -> None:
    """Attempt to fire a lifecycle hook for *extension_name*.

    Silently skips if the extension module or hook is not available.
    """
    try:
        from app.common.extension_hooks import run_hook

        run_hook(extension_name, event)
        logger.info("Fired '%s' hook for extension '%s'.", event, extension_name)
    except Exception:
        logger.debug("No '%s' hook available for '%s'.", event, extension_name)


# ── CLI entry point ───────────────────────────────────────────────────


def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate command."""
    parser = argparse.ArgumentParser(
        prog="extension_manager",
        description="Powercord Extension Manager — install, uninstall, and list extensions.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # install
    install_parser = subparsers.add_parser("install", help="Install an extension from a local path")
    install_parser.add_argument("path", help="Path to the extension directory")

    # uninstall
    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall an extension by name")
    uninstall_parser.add_argument("name", help="Extension name to uninstall")

    # list
    subparsers.add_parser("list", help="List all installed extensions")

    args = parser.parse_args()

    if args.command == "install":
        install_extension(args.path)
    elif args.command == "uninstall":
        uninstall_extension(args.name)
    elif args.command == "list":
        list_extensions()
    else:
        parser.print_help()


__all__ = [
    "EXTENSIONS_DIR",
    "TESTS_DIR",
    "_fire_hook",
    "_normalize_pkg_name",
    "_update_alembic_ini",
    "get_installed_extensions",
    "install_extension",
    "list_extensions",
    "load_manifest",
    "main",
    "uninstall_extension",
]


if __name__ == "__main__":
    main()
