"""Version Parity and Extension Manifest Governance Tests for Powercord.

Governed by:
- inv-manifest-version-parity: Extension Manifest & Pyproject Version Parity
- inv-alembic-lineage-isolation: Multi-Head Alembic Migration Lineage Isolation
- inv-widget-scope-namespaces: FastHTML Widget Prefix Scoping
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent
CLIENT_ROOT = WORKSPACE_ROOT / "powercord-client"
DOWNSTREAM_ROOT = WORKSPACE_ROOT / "powercord-downstream-server"
EXTENSIONS_ROOT = WORKSPACE_ROOT / "powercord-extensions"
APP_EXTENSIONS_ROOT = REPO_ROOT / "app" / "extensions"

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _read_pyproject_version(path: Path) -> str | None:
    if not path.exists():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if "tool" in data and "poetry" in data["tool"] and "version" in data["tool"]["poetry"]:
        return str(data["tool"]["poetry"]["version"])
    if "project" in data and "version" in data["project"]:
        return str(data["project"]["version"])
    return None


def _parse_semver(version: str | None) -> tuple[int, int, int] | None:
    if not version:
        return None
    match = SEMVER_RE.match(version.strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _validate_default_widgets(source: Path, widgets: list[dict[str, Any]], violations: list[str]) -> None:
    """Validate widget column_span (1-12) and admin_/guild_admin_ scope prefixes."""
    for widget in widgets:
        w_name = str(widget.get("widget_name", ""))
        span = widget.get("column_span", 0)
        if not isinstance(span, int) or not (1 <= span <= 12):
            violations.append(f"{source}: Widget {w_name} column_span must be 1-12, got {span}")

        if not (w_name.startswith("admin_") or w_name.startswith("guild_admin_") or "admin" not in w_name):
            violations.append(f"{source}: Widget {w_name} violates prefix scoping rules")


@pytest.mark.unit
def test_ecosystem_baseline_versions() -> None:
    """Verify valid SemVer across core packages (treating ephemeral downstream as non-blocking)."""
    powercord_version = _read_pyproject_version(REPO_ROOT / "pyproject.toml")
    assert powercord_version is not None, "powercord version must be defined in pyproject.toml"
    assert _parse_semver(powercord_version) is not None, (
        f"Invalid SemVer in powercord/pyproject.toml: {powercord_version}"
    )

    if WORKSPACE_ROOT == Path("/") or not WORKSPACE_ROOT.exists():
        pytest.skip(f"Ecosystem multi-repo root not available in container environment: {WORKSPACE_ROOT}")

    if DOWNSTREAM_ROOT.exists():
        downstream_version = _read_pyproject_version(DOWNSTREAM_ROOT / "pyproject.toml")
        assert _parse_semver(downstream_version) is not None, (
            f"Invalid SemVer in ephemeral powercord-downstream-server/pyproject.toml: {downstream_version}"
        )

    if CLIENT_ROOT.exists():
        client_version = _read_pyproject_version(CLIENT_ROOT / "pyproject.toml")
        parsed_client = _parse_semver(client_version)
        assert parsed_client is not None and parsed_client >= (1, 0, 0), (
            f"powercord-client version must be valid SemVer >= 1.0.0, got: {client_version}"
        )


@pytest.mark.unit
def test_extension_manifest_and_pyproject_parity() -> None:
    """Verify extension.json and [tool.powercord] pyproject.toml version parity and widget schema conventions."""
    all_extensions: list[Path] = []
    if APP_EXTENSIONS_ROOT.exists():
        all_extensions.extend(
            [d for d in sorted(APP_EXTENSIONS_ROOT.iterdir()) if d.is_dir() and not d.name.startswith((".", "__"))]
        )
    if EXTENSIONS_ROOT.exists():
        all_extensions.extend(
            [d for d in sorted(EXTENSIONS_ROOT.iterdir()) if d.is_dir() and not d.name.startswith((".", "__"))]
        )

    violations: list[str] = []

    for ext_dir in all_extensions:
        manifest_path = ext_dir / "extension.json"
        pyproject_path = ext_dir / "pyproject.toml"

        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as e:
                violations.append(f"{manifest_path}: Invalid JSON ({e})")
                continue

            manifest_version = manifest.get("version")
            if not manifest_version:
                violations.append(f"{manifest_path}: Missing 'version' field")

            if pyproject_path.exists():
                py_ver = _read_pyproject_version(pyproject_path)
                if py_ver != manifest_version:
                    violations.append(
                        f"{ext_dir.name}: Version mismatch! extension.json='{manifest_version}' != pyproject.toml='{py_ver}'"
                    )

            _validate_default_widgets(manifest_path, manifest.get("default_widgets", []), violations)

        if pyproject_path.exists():
            try:
                pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            except Exception as e:
                violations.append(f"{pyproject_path}: Invalid TOML ({e})")
                continue

            py_ver = _read_pyproject_version(pyproject_path)
            if not _parse_semver(py_ver):
                violations.append(f"{pyproject_path}: Missing or invalid SemVer version '{py_ver}'")

            tool_powercord = pyproject_data.get("tool", {}).get("powercord")
            if isinstance(tool_powercord, dict):
                raw_widgets = tool_powercord.get("default_widgets", [])
                if not isinstance(raw_widgets, list):
                    violations.append(f"{pyproject_path}: [tool.powercord.default_widgets] must be a list of tables")
                else:
                    _validate_default_widgets(pyproject_path, raw_widgets, violations)
            elif not manifest_path.exists():
                violations.append(
                    f"{ext_dir.name}: Missing both extension.json and [tool.powercord] metadata in pyproject.toml"
                )

    assert not violations, "\n".join(violations)


@pytest.mark.unit
def test_alembic_multi_head_isolation() -> None:
    """Verify that extensions maintain independent Alembic migration lineages."""
    if not EXTENSIONS_ROOT.exists():
        pytest.skip(f"powercord-extensions directory not found at {EXTENSIONS_ROOT} (isolated container environment)")

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
