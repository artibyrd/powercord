"""Powercord Extension Manager — install, uninstall, and list extensions.

Provides a CLI interface (invoked via ``python -m app.common.extension_manager``)
and importable helpers for managing the extension lifecycle.  Each extension is
expected to ship an ``extension.json`` manifest (see schema in README).

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
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

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


# ── Manifest helpers ──────────────────────────────────────────────────


def load_manifest(extension_path: Path) -> dict[str, Any]:
    """Load and validate an ``extension.json`` manifest from *extension_path*.

    Raises ``FileNotFoundError`` if the manifest is missing, or
    ``ValueError`` if required keys are absent.
    """
    manifest_file = extension_path / "extension.json"
    if not manifest_file.is_file():
        raise FileNotFoundError(f"No extension.json found in {extension_path}")

    with open(manifest_file, encoding="utf-8") as fh:
        manifest: dict[str, Any] = json.load(fh)

    # Validate required keys
    required_keys = ["name", "version", "description"]
    missing = [k for k in required_keys if k not in manifest]
    if missing:
        raise ValueError(f"extension.json missing required keys: {missing}")

    return manifest


def get_installed_extensions() -> list[dict[str, Any]]:
    """Return a list of manifest dicts for every installed extension."""
    extensions: list[dict[str, Any]] = []
    for ext_path in sorted(EXTENSIONS_DIR.iterdir()):
        if not ext_path.is_dir() or ext_path.name.startswith((".", "__")):
            continue
        try:
            manifest = load_manifest(ext_path)
            manifest["_path"] = str(ext_path)
            extensions.append(manifest)
        except (FileNotFoundError, ValueError):
            # Legacy extension without a manifest — still list it, but with minimal info
            extensions.append(
                {
                    "name": ext_path.name,
                    "version": "unknown",
                    "description": "(no extension.json)",
                    "internal": False,
                    "_path": str(ext_path),
                }
            )
    return extensions


# ── Install ───────────────────────────────────────────────────────────


def install_extension(source_path: str | Path) -> None:
    """Install an extension from *source_path* into the extensions directory.

    Steps:
    1. Read and validate the manifest.
    2. Copy extension files into ``app/extensions/<name>/``.
    3. Install any declared Python dependencies via ``poetry add``.
    4. Run ``alembic upgrade head`` if the extension declares migrations.
    5. Fire the ``on_install`` lifecycle hook if one is registered.
    """
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
        if is_reinstall and set(deps) == set(old_deps):
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
            try:
                subprocess.run(  # noqa: S603
                    [_POETRY_CMD, "run", "alembic", "upgrade", "head"],  # noqa: S607
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

    # 2. Remove Python dependencies (only those unique to this extension)
    deps_raw = manifest.get("python_dependencies", [])
    deps: list[str] = [str(d) for d in deps_raw] if isinstance(deps_raw, list) else []
    if deps:
        # Collect deps used by OTHER installed extensions so we don't remove shared ones
        other_deps: set[str] = set()
        for ext in get_installed_extensions():
            if ext["name"] != name:
                for dep in ext.get("python_dependencies", []):
                    # Normalize to just the package name (strip version specifiers)
                    other_deps.add(dep.split(">=")[0].split("<=")[0].split("==")[0].split("<")[0].split(">")[0].strip())

        unique_deps = []
        for dep in deps:
            pkg_name = dep.split(">=")[0].split("<=")[0].split("==")[0].split("<")[0].split(">")[0].strip()
            if pkg_name not in other_deps:
                unique_deps.append(pkg_name)

        if unique_deps:
            print(f"  📦 Removing {len(unique_deps)} unique dependencies...")
            try:
                subprocess.run(  # noqa: S603
                    [_POETRY_CMD, "remove", *unique_deps],  # noqa: S607
                    check=True,
                    cwd=str(EXTENSIONS_DIR.parents[1]),
                )
                print("  ✅ Dependencies removed.")
            except subprocess.CalledProcessError as exc:
                print(f"  ⚠️  Failed to remove some dependencies: {exc}")
                print("     Note: On Windows, make sure the server is stopped so files aren't locked.")
                print("     Aborting uninstallation. Stop the server and try again.")
                sys.exit(1)

    # 3. Remove extension directory
    shutil.rmtree(dest)
    print(f"  ✅ Removed {dest}")

    # 3b. Remove extension tests from the framework test directory
    test_dest = TESTS_DIR / name
    if test_dest.exists():
        shutil.rmtree(test_dest)
        print(f"  ✅ Removed tests from {test_dest}")

    # 4. Warn about orphaned database tables
    if manifest.get("has_migrations", False):
        print(f"  ⚠️  Extension '{name}' had database tables.")
        print("     These tables still exist in your database.")
        print("     To fully clean up, manually drop the tables or create a down-migration.")

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
        # Hook not registered or extension module not importable — that's fine
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


if __name__ == "__main__":
    main()
