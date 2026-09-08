"""Architecture and Modularity Governance Tests for Powercord.

Governed by:
- inv-500-loc-ceiling: 500 LOC Module Ceiling Law with Ratchet
- inv-compute-ontology: Pure Function Ontology (compute_*)
- inv-client-server-decoupling: Client-Server Runtime Isolation
- inv-source-isolation-no-ad-hoc-cp: Core Extension Directory Isolation
"""

from __future__ import annotations

import ast
import json
import re
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


@pytest.mark.unit
def test_core_extensions_directory_isolation() -> None:
    """Verify that core powercord repository contains ONLY internal extensions (inv-source-isolation-no-ad-hoc-cp)."""
    from app.common.extension_manager import _is_core_repository

    if not _is_core_repository(REPO_ROOT):
        pytest.skip("Extension directory isolation is enforced on core powercord repo only.")

    extensions_dir = SRC_ROOT / "extensions"
    assert extensions_dir.exists(), f"Missing extensions directory at {extensions_dir}"

    allowed_internal_extensions = {"custom_content", "example", "utilities"}
    found_extensions = {d.name for d in extensions_dir.iterdir() if d.is_dir() and not d.name.startswith((".", "__"))}

    external_extensions = found_extensions - allowed_internal_extensions
    assert not external_extensions, (
        f"External extension(s) found in core framework repository: {external_extensions}.\n"
        "Per inv-source-isolation-no-ad-hoc-cp, external extensions must NOT be installed into the "
        "powercord core repository. Install extensions exclusively in powercord-downstream-server/."
    )


@pytest.mark.unit
def test_no_raw_generator_session_leak_invariant() -> None:
    """Verify that get_session() generator is never manually invoked via direct call in application code.

    Calling get_session() directly creates an unmanaged generator that leaks database sessions
    and exhausts connection pools when early returning or failing.
    - In FastAPI routes, use dependency injection: 'session: Session = Depends(get_session)'
    - In Discord cogs, jobs, and standalone code, use RAII: 'with Session(engine) as session:'
    """
    violations = []
    roots_to_scan = [SRC_ROOT]
    extensions_root = REPO_ROOT.parent / "powercord-extensions"
    if extensions_root.exists():
        roots_to_scan.append(extensions_root)

    for root in roots_to_scan:
        for py_file in root.rglob("*.py"):
            if ".venv" in py_file.parts or "__pycache__" in py_file.parts or "tests" in py_file.parts:
                continue
            if py_file.name == "alchemy.py":
                continue

            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"), filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "get_session":
                        rel_path = (
                            str(py_file.relative_to(REPO_ROOT))
                            if REPO_ROOT in py_file.parents
                            else str(py_file.relative_to(REPO_ROOT.parent))
                        )
                        violations.append((rel_path, node.lineno))
            except Exception:
                pass

    assert not violations, (
        f"Raw generator session leak detected: direct call to get_session() at {violations}.\n"
        "Directly invoking get_session() creates an unmanaged generator. "
        "In FastAPI routes, pass Depends(get_session). In standalone code/cogs, use 'with Session(engine) as session:'."
    )


# ==============================================================================
# Invariant: Headless Matplotlib in Multi-Threaded Workers
# ==============================================================================


@pytest.mark.unit
def test_matplotlib_headless_backend_invariant() -> None:
    """Verify that any file importing matplotlib.pyplot configures headless Agg backend.

    Matplotlib defaults to Tkinter GUI on Linux if unconfigured, causing fatal SIGABRT /
    'Tcl_AsyncDelete: async handler deleted by the wrong thread' crashes when run in
    ThreadPoolExecutor or asyncio worker threads. Files importing pyplot must configure
    matplotlib.use("Agg") prior to import.
    """
    violations = []
    roots_to_scan = [SRC_ROOT]
    ext_root = REPO_ROOT.parent / "powercord-extensions"
    if ext_root.exists():
        roots_to_scan.append(ext_root)

    for root in roots_to_scan:
        for py_file in root.rglob("*.py"):
            if ".venv" in py_file.parts or "__pycache__" in py_file.parts or "tests" in py_file.parts:
                continue

            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if "pyplot" in content:
                tree = ast.parse(content, filename=str(py_file))
                has_pyplot = False
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if "pyplot" in alias.name:
                                has_pyplot = True
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and "matplotlib" in node.module:
                            for alias in node.names:
                                if alias.name == "pyplot":
                                    has_pyplot = True

                if has_pyplot:
                    if 'matplotlib.use("Agg")' not in content and "matplotlib.use('Agg')" not in content:
                        rel_path = (
                            str(py_file.relative_to(REPO_ROOT))
                            if REPO_ROOT in py_file.parents
                            else str(py_file.relative_to(REPO_ROOT.parent))
                        )
                        violations.append(rel_path)

    assert not violations, (
        f"Files importing matplotlib.pyplot without configuring headless 'Agg' backend: {violations}.\n"
        "Configure matplotlib.use('Agg') before importing pyplot to prevent Tkinter multi-threading crashes."
    )


# ==============================================================================
# Invariant: Physical Storage Authority (No Derived Asset DB Columns)
# ==============================================================================

FORBIDDEN_ASSET_COLUMN_RE = re.compile(
    r"^has_(png|jpg|jpeg|image|file|audio|midi|asset|cache|thumbnail)$|^is_cached$",
    re.IGNORECASE,
)


@pytest.mark.unit
def test_no_derived_asset_columns_in_database_models() -> None:
    """Verify that SQLModel schemas never declare derived file/cache existence columns.

    Per inv-omission-over-fallback-galleries, physical storage is the single source of truth.
    Storing 'has_png' or 'is_cached' in database schemas introduces split authority and desync
    when files are deleted or moved out-of-band. Derived assets must be detected at runtime
    and repaired via background queues.
    """
    violations = []
    roots_to_scan = [SRC_ROOT]
    ext_root = REPO_ROOT.parent / "powercord-extensions"
    if ext_root.exists():
        roots_to_scan.append(ext_root)

    for root in roots_to_scan:
        for py_file in root.rglob("*.py"):
            if ".venv" in py_file.parts or "__pycache__" in py_file.parts or "tests" in py_file.parts:
                continue
            if py_file.name not in ("models.py", "blueprint.py"):
                continue

            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        field_name = None
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                            field_name = item.target.id
                        elif isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    field_name = target.id

                        if field_name and FORBIDDEN_ASSET_COLUMN_RE.match(field_name):
                            rel_path = (
                                str(py_file.relative_to(REPO_ROOT))
                                if REPO_ROOT in py_file.parents
                                else str(py_file.relative_to(REPO_ROOT.parent))
                            )
                            violations.append((rel_path, node.name, field_name, getattr(item, "lineno", 0)))

    assert not violations, (
        f"Derived asset existence columns detected in database models: {violations}.\n"
        "Per inv-omission-over-fallback-galleries, physical storage is the authority. "
        "Do not store asset flags (has_png, is_cached) in database schemas; handle via runtime detection and repair queues."
    )


# ==============================================================================
# Invariant: Discord Status Edit Component Dismissal Sentinel
# ==============================================================================


@pytest.mark.unit
def test_discord_status_edit_component_sentinel_invariant() -> None:
    """Verify that Discord status editing helpers do not drop view=None via 'if view is not None'.

    In Nextcord / Discord API, omitting the view parameter leaves existing message components intact.
    Status edit helpers must distinguish between an unset view (sentinel default) and explicitly
    clearing components (view=None). Checking 'if view is not None: kwargs['view'] = view' prevents
    button dismissal upon job completion.
    """
    violations = []
    roots_to_scan = [SRC_ROOT]
    ext_root = REPO_ROOT.parent / "powercord-extensions"
    if ext_root.exists():
        roots_to_scan.append(ext_root)

    for root in roots_to_scan:
        for py_file in root.rglob("*.py"):
            if ".venv" in py_file.parts or "__pycache__" in py_file.parts or "tests" in py_file.parts:
                continue

            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if "status_edit" not in content:
                continue

            tree = ast.parse(content, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "status_edit" in node.name:
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.If) and isinstance(sub.test, ast.Compare):
                            test = sub.test
                            if isinstance(test.left, ast.Name) and test.left.id == "view":
                                for op, comp in zip(test.ops, test.comparators, strict=False):
                                    if (
                                        isinstance(op, ast.IsNot)
                                        and isinstance(comp, ast.Constant)
                                        and comp.value is None
                                    ):
                                        rel_path = (
                                            str(py_file.relative_to(REPO_ROOT))
                                            if REPO_ROOT in py_file.parents
                                            else str(py_file.relative_to(REPO_ROOT.parent))
                                        )
                                        violations.append((rel_path, node.name, sub.lineno))

    assert not violations, (
        f"Status edit helper discarding explicit view=None at {violations}.\n"
        "Use a sentinel default (e.g. _VIEW_UNSET = object()) and check 'if view is not _VIEW_UNSET:' "
        "so that explicitly passing view=None forwards view=None to Discord to clear interactive buttons."
    )
