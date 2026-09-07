"""Version Parity and Extension Manifest Governance Tests for Powercord.

Governed by:
- inv-manifest-version-parity: Extension Manifest & Pyproject Version Parity
- inv-alembic-lineage-isolation: Multi-Head Alembic Migration Lineage Isolation
- inv-widget-scope-namespaces: FastHTML Widget Prefix Scoping
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent
CLIENT_ROOT = WORKSPACE_ROOT / "powercord-client"
DOWNSTREAM_ROOT = WORKSPACE_ROOT / "powercord-downstream-server"
EXTENSIONS_ROOT = WORKSPACE_ROOT / "powercord-extensions"
APP_EXTENSIONS_ROOT = REPO_ROOT / "app" / "extensions"


def _read_pyproject_version(path: Path) -> str | None:
    if not path.exists():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if "tool" in data and "poetry" in data["tool"] and "version" in data["tool"]["poetry"]:
        return str(data["tool"]["poetry"]["version"])
    if "project" in data and "version" in data["project"]:
        return str(data["project"]["version"])
    return None


@pytest.mark.unit
def test_ecosystem_baseline_versions() -> None:
    """Verify true baseline version alignment across core packages."""
    powercord_version = _read_pyproject_version(REPO_ROOT / "pyproject.toml")
    assert powercord_version is not None, "powercord version must be defined in pyproject.toml"

    if DOWNSTREAM_ROOT.exists():
        downstream_version = _read_pyproject_version(DOWNSTREAM_ROOT / "pyproject.toml")
        assert downstream_version == powercord_version, (
            f"powercord-downstream-server must mirror core {powercord_version}, got: {downstream_version}"
        )

    if CLIENT_ROOT.exists():
        client_version = _read_pyproject_version(CLIENT_ROOT / "pyproject.toml")
        assert client_version == "1.0.0", f"powercord-client version must be 1.0.0, got: {client_version}"


@pytest.mark.unit
def test_extension_manifest_and_pyproject_parity() -> None:
    """Verify that extension.json version matches pyproject.toml and follows schema conventions."""
    all_extensions = []
    if APP_EXTENSIONS_ROOT.exists():
        all_extensions.extend([d for d in APP_EXTENSIONS_ROOT.iterdir() if d.is_dir()])
    if EXTENSIONS_ROOT.exists():
        all_extensions.extend([d for d in EXTENSIONS_ROOT.iterdir() if d.is_dir()])

    violations = []

    for ext_dir in all_extensions:
        manifest_path = ext_dir / "extension.json"
        if not manifest_path.exists():
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            violations.append(f"{manifest_path}: Invalid JSON ({e})")
            continue

        manifest_version = manifest.get("version")
        if not manifest_version:
            violations.append(f"{manifest_path}: Missing 'version' field")

        pyproject_path = ext_dir / "pyproject.toml"
        if pyproject_path.exists():
            py_ver = _read_pyproject_version(pyproject_path)
            if py_ver != manifest_version:
                violations.append(
                    f"{ext_dir.name}: Version mismatch! extension.json='{manifest_version}' != pyproject.toml='{py_ver}'"
                )

        # Validate widget schema and scoping prefixes
        for widget in manifest.get("default_widgets", []):
            w_name = widget.get("widget_name", "")
            span = widget.get("column_span", 0)
            if not (1 <= span <= 12):
                violations.append(f"{manifest_path}: Widget {w_name} column_span must be 1-12, got {span}")

            # Verify widget scope prefix convention
            if not (w_name.startswith("admin_") or w_name.startswith("guild_admin_") or "admin" not in w_name):
                violations.append(f"{manifest_path}: Widget {w_name} violates prefix scoping rules")

    assert not violations, "\n".join(violations)


@pytest.mark.unit
def test_alembic_multi_head_isolation() -> None:
    """Verify that extensions maintain independent Alembic migration lineages."""
    if not EXTENSIONS_ROOT.exists():
        return

    violations = []
    for ext_dir in EXTENSIONS_ROOT.iterdir():
        versions_dir = ext_dir / "alembic" / "versions"
        if not versions_dir.exists():
            continue

        migration_files = list(versions_dir.glob("*.py"))
        for m_file in migration_files:
            content = m_file.read_text(encoding="utf-8")
            # Extensions should either have down_revision = None or branch off their own extension heads
            if "down_revision = 'core" in content:
                violations.append(f"{m_file}: Disallowed cross-lineage dependency on core server migration head")

    assert not violations, "\n".join(violations)
