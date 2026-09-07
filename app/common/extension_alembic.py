"""Alembic configuration management for Powercord extensions."""

from __future__ import annotations

import configparser
from pathlib import Path


def _update_alembic_ini(extensions_dir: Path | None = None) -> None:
    """Dynamically reconstructs version_locations in alembic.ini based on active extensions."""
    if extensions_dir is None:
        extensions_dir = Path(__file__).resolve().parents[1] / "extensions"

    ini_path = extensions_dir.parents[1] / "alembic.ini"
    if not ini_path.exists():
        return

    config = configparser.ConfigParser()
    config.read(ini_path)

    paths = ["%(here)s/alembic/versions"]
    if extensions_dir.exists():
        for d in extensions_dir.iterdir():
            if d.is_dir() and (d / "alembic" / "versions").exists():
                paths.append(f"%(here)s/app/extensions/{d.name}/alembic/versions")

    if "alembic" not in config.sections():
        config.add_section("alembic")

    config.set("alembic", "version_locations", " ".join(paths))
    with open(ini_path, "w", encoding="utf-8") as configfile:
        config.write(configfile)
