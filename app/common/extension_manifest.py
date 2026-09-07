"""Extension manifest loading and dependency normalization."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any


def _normalize_pkg_name(dep: str) -> str:
    """Strip version specifiers from a dependency string.

    For example ``"pretty-midi>=0.2.11"`` → ``"pretty-midi"``.
    """
    for sep in (">", "<", "=", "!", "~", "[", "@"):
        dep = dep.split(sep, 1)[0]
    return dep.strip()


def load_manifest(extension_path: Path) -> dict[str, Any]:
    """Load and validate an extension's metadata from ``pyproject.toml`` or ``extension.json``.

    Raises ``FileNotFoundError`` if no manifest file is found, or
    ``ValueError`` if required keys are absent.
    """
    toml_file = extension_path / "pyproject.toml"
    json_file = extension_path / "extension.json"

    if toml_file.is_file():
        with open(toml_file, "rb") as fh:
            doc = tomllib.load(fh)

        # Validate required keys
        poetry_meta = doc.get("tool", {}).get("poetry", {})
        required_keys = ["name", "version", "description"]
        missing = [k for k in required_keys if k not in poetry_meta]
        if missing:
            raise ValueError(f"pyproject.toml [tool.poetry] missing required keys: {missing}")

        powercord_meta = doc.get("tool", {}).get("powercord", {})

        deps_raw = poetry_meta.get("dependencies", {})
        # Skip standard framework dependencies and python identifier
        deps = []
        for pkg, version in deps_raw.items():
            if pkg in ("python", "powercord"):
                continue
            # Support inline tables like git/path dependencies or simple versions
            if isinstance(version, str):
                deps.append(f"{pkg}@{version}")
            elif isinstance(version, dict):
                deps.append(pkg)

        manifest = {
            "name": poetry_meta["name"],
            "version": poetry_meta["version"],
            "description": poetry_meta["description"],
            "python_dependencies": deps,
            "discord_permissions": powercord_meta.get("discord_permissions", []),
            "has_migrations": powercord_meta.get("has_migrations", False),
            "latest_migration_version": powercord_meta.get("latest_migration_version", None),
            "internal": powercord_meta.get("internal", False),
            "default_widgets": powercord_meta.get("default_widgets", []),
        }
        return manifest

    elif json_file.is_file():
        with open(json_file, encoding="utf-8") as fh:
            manifest = json.load(fh)

        required_keys = ["name", "version", "description"]
        missing = [k for k in required_keys if k not in manifest]
        if missing:
            raise ValueError(f"extension.json missing required keys: {missing}")

        manifest_dict = dict(manifest)
        if "default_widgets" not in manifest_dict:
            manifest_dict["default_widgets"] = []
        return manifest_dict

    raise FileNotFoundError(f"No pyproject.toml or extension.json found in {extension_path}")


def get_installed_extensions(extensions_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return a list of manifest dicts for every installed extension."""
    if extensions_dir is None:
        extensions_dir = Path(__file__).resolve().parents[1] / "extensions"

    extensions: list[dict[str, Any]] = []
    if not extensions_dir.exists():
        return extensions

    for ext_path in sorted(extensions_dir.iterdir()):
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
                    "description": "(no valid manifest)",
                    "internal": False,
                    "_path": str(ext_path),
                }
            )
    return extensions
