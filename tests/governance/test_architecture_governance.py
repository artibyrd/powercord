"""Architecture and Modularity Governance Tests for Powercord.

Governed by:
- inv-500-loc-ceiling: 500 LOC Module Ceiling Law with Ratchet
- inv-compute-ontology: Pure Function Ontology (compute_*)
- inv-client-server-decoupling: Client-Server Runtime Isolation
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "app"
CLIENT_ROOT = REPO_ROOT.parent / "powercord-client"
RATCHET_PATH = Path(__file__).parent / "governance_ratchet.json"


@pytest.mark.unit
def test_500_loc_ceiling_with_ratchet() -> None:
    """Verify 500 LOC ceiling for all new code and monotonic ratchet decreases for legacy debt."""
    assert RATCHET_PATH.exists(), f"Missing architectural debt ratchet: {RATCHET_PATH}"
    ratchet_data = json.loads(RATCHET_PATH.read_text(encoding="utf-8"))
    ratchet_files = ratchet_data.get("files", {})

    violations = []
    graduations = []
    active_debt_lines = 0

    print("\n" + "=" * 76)
    print("                 POWERCORD ARCHITECTURAL DEBT DASHBOARD")
    print("=" * 76)

    for py_file in sorted(SRC_ROOT.rglob("*.py")):
        if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
            continue

        rel_path = str(py_file.relative_to(REPO_ROOT))
        line_count = len(py_file.read_text(encoding="utf-8", errors="ignore").splitlines())

        if rel_path in ratchet_files:
            max_allowed = ratchet_files[rel_path]["max_loc"]
            target_milestone = ratchet_files[rel_path].get("target_milestone", "future")
            active_debt_lines += line_count

            if line_count > max_allowed:
                violations.append(
                    f"Ratchet breach: {rel_path} has {line_count} LOC (max frozen ceiling was {max_allowed})"
                )
            elif line_count <= 500:
                graduations.append((rel_path, line_count))
            else:
                print(f"  [PROBATION] {rel_path:<48} : {line_count:>4} / {max_allowed:>4} LOC ({target_milestone})")
        else:
            if line_count > 500:
                violations.append(
                    f"New/unregistered file exceeding 500 LOC: {rel_path} has {line_count} LOC (limit is 500)"
                )

    print("-" * 76)
    print(f"  Active Probation Files : {len(ratchet_files) - len(graduations)} / {len(ratchet_files)}")
    print(f"  Total Ratcheted Debt   : {active_debt_lines} LOC")
    if graduations:
        print(f"  Eligible for Graduation: {len(graduations)} file(s):")
        for g_file, g_loc in graduations:
            print(f"    - {g_file} is down to {g_loc} LOC! (Remove from governance_ratchet.json)")
    print("=" * 76 + "\n")

    assert not violations, "\n".join(violations)


@pytest.mark.unit
def test_compute_naming_ontology_invariant() -> None:
    """Verify that calculation functions adhere strictly to compute_* naming (banning calc_* / calculate_*)."""
    disallowed_prefixes = ("calculate_", "calc_")
    violations = []

    for py_file in SRC_ROOT.rglob("*.py"):
        if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if any(node.name.startswith(p) for p in disallowed_prefixes):
                        violations.append((str(py_file.relative_to(REPO_ROOT)), node.name, node.lineno))
        except Exception:
            pass

    assert not violations, f"Functions violating compute_* naming ontology: {violations}"


@pytest.mark.unit
def test_client_server_runtime_isolation() -> None:
    """Verify that companion desktop client code never imports backend server packages."""
    if not CLIENT_ROOT.exists():
        pytest.skip(f"powercord-client not found at {CLIENT_ROOT}")

    disallowed_modules = ("app", "nextcord", "fasthtml")
    violations = []

    for py_file in CLIENT_ROOT.rglob("*.py"):
        if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in disallowed_modules:
                            violations.append((str(py_file.relative_to(CLIENT_ROOT)), alias.name, node.lineno))
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in disallowed_modules:
                        violations.append((str(py_file.relative_to(CLIENT_ROOT)), node.module, node.lineno))
        except Exception:
            pass

    assert not violations, f"Client importing backend server modules: {violations}"
