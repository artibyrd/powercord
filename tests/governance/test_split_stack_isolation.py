"""Split-Stack Architecture Isolation Governance Tests.

Governed by:
- inv-split-stack-isolation: FastHTML HTMX vs FastAPI REST Isolation
- inv-fasthtml-card-signature: FastHTML Card Integrity & Signature Preservation
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "app"


@pytest.mark.unit
def test_sprockets_never_import_fasthtml() -> None:
    """Verify that FastAPI REST sprockets never import FastHTML UI components."""
    violations = []

    for py_file in SRC_ROOT.rglob("*sprocket*.py"):
        if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
            continue

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "fasthtml" in alias.name:
                            violations.append((str(py_file.relative_to(REPO_ROOT)), alias.name, node.lineno))
                elif isinstance(node, ast.ImportFrom):
                    if node.module and "fasthtml" in node.module:
                        violations.append((str(py_file.relative_to(REPO_ROOT)), node.module, node.lineno))
        except Exception:
            pass

    assert not violations, f"Sprockets violating split-stack isolation by importing FastHTML: {violations}"


@pytest.mark.unit
def test_routes_do_not_return_raw_dict_json() -> None:
    """Verify that FastHTML @rt routes do not import FastAPI Response objects."""
    violations = []

    for py_file in SRC_ROOT.rglob("routes.py"):
        if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            # Route files should not return JSONResponse directly
            if "JSONResponse" in content:
                violations.append(str(py_file.relative_to(REPO_ROOT)))
        except Exception:
            pass

    assert not violations, f"FastHTML routes returning JSONResponse instead of FT components: {violations}"
