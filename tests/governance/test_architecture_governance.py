"""Architecture and Modularity Governance Tests for Powercord.

Governed by:
- inv-500-loc-ceiling: Deep Modules (~500 LOC soft trigger) + 1,000-LOC Anti-God-File Safety Rail
- inv-compute-ontology: Pure Function Ontology (compute_*)
- inv-client-server-decoupling: Client-Server Runtime Isolation
- inv-source-isolation-no-ad-hoc-cp: Core Extension Directory Isolation
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent
SRC_ROOT = REPO_ROOT / "app"
CLIENT_ROOT = WORKSPACE_ROOT / "powercord-client"
EXTENSIONS_ROOT = WORKSPACE_ROOT / "powercord-extensions"
CLIENT_EXTENSIONS_ROOT = WORKSPACE_ROOT / "powercord-client-extensions"

HARD_LOC_CEILING = 1000
VENDOR_IDE_DOTFOLDERS = {".gemini", ".vscode", ".cursor", ".idea"}
MACHINE_LOCAL_PATH_RE = re.compile(r"(?:/home/|/Users/)[A-Za-z0-9._-]+/")
DEFAULT_SKIP_DIRS = {".venv", "__pycache__", ".git", ".mypy_cache", ".ruff_cache", ".pytest_cache", "node_modules"}


def _iter_files(
    root: Path,
    *,
    suffixes: set[str] | None = None,
    names: set[str] | None = None,
    skip_dirs: set[str] = DEFAULT_SKIP_DIRS,
) -> Iterator[Path]:
    """Walk root while pruning skipped directories in-place (avoids descending into .venv/.git)."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip_dirs)
        base = Path(dirpath)
        for fname in sorted(filenames):
            fpath = base / fname
            if suffixes is None and names is None:
                yield fpath
            elif (suffixes and fpath.suffix in suffixes) or (names and fname in names):
                yield fpath


def _discover_ecosystem_git_repos() -> list[Path]:
    """Return existing git repositories in the workspace, always starting with REPO_ROOT."""
    repos: list[Path] = [REPO_ROOT]
    if WORKSPACE_ROOT == Path("/") or not WORKSPACE_ROOT.exists():
        return repos

    fixed_siblings = [
        WORKSPACE_ROOT / "powercord-agent",
        CLIENT_ROOT,
        WORKSPACE_ROOT / "powercord-downstream-server",
    ]
    for candidate in fixed_siblings:
        if candidate.is_dir() and (candidate / ".git").exists():
            repos.append(candidate)

    for group_dir in (EXTENSIONS_ROOT, CLIENT_EXTENSIONS_ROOT):
        if group_dir.is_dir():
            for child in sorted(group_dir.iterdir()):
                if child.is_dir() and (child / ".git").exists():
                    repos.append(child)

    return repos


@pytest.mark.unit
def test_1000_loc_anti_god_file_safety_rail() -> None:
    """Verify the 1,000-LOC anti-god-file safety rail across core, client, and extensions.

    Powercord adopts Ousterhout Deep Modules (~500 LOC soft decomposition trigger in
    .agents/overrides/architecture-review.md) backed by a hard 1,000-LOC ceiling here.
    """
    roots_to_scan: list[Path] = [SRC_ROOT]
    if CLIENT_ROOT.exists():
        roots_to_scan.append(CLIENT_ROOT)
    if EXTENSIONS_ROOT.exists():
        roots_to_scan.append(EXTENSIONS_ROOT)

    violations: list[str] = []
    skipped_parts = DEFAULT_SKIP_DIRS | {"tests", "alembic"}

    for root in roots_to_scan:
        for py_file in _iter_files(root, suffixes={".py"}, skip_dirs=skipped_parts):
            line_count = len(py_file.read_text(encoding="utf-8", errors="ignore").splitlines())
            if line_count > HARD_LOC_CEILING:
                rel_path = (
                    str(py_file.relative_to(REPO_ROOT))
                    if REPO_ROOT in py_file.parents
                    else str(py_file.relative_to(WORKSPACE_ROOT))
                )
                violations.append(
                    f"God-file safety rail breach: {rel_path} has {line_count} LOC (hard limit is {HARD_LOC_CEILING})"
                )

    assert not violations, "\n".join(violations)


@pytest.mark.unit
def test_zero_tracked_vendor_ide_dotfolders() -> None:
    """Verify zero tracked vendor IDE/agent dotfolders and .gemini/ presence in .gitignore."""
    git_bin = shutil.which("git")
    repos = _discover_ecosystem_git_repos()

    tracked_violations: list[str] = []
    gitignore_violations: list[str] = []

    for repo in repos:
        gitignore_path = repo / ".gitignore"
        if not gitignore_path.exists():
            gitignore_violations.append(f"{repo.name}: missing .gitignore")
        else:
            lines = {line.strip() for line in gitignore_path.read_text(encoding="utf-8").splitlines()}
            if ".gemini/" not in lines and ".gemini" not in lines:
                gitignore_violations.append(f"{repo.name}/.gitignore: missing '.gemini/' entry")

        if git_bin and (repo / ".git").exists():
            proc = subprocess.run(
                [git_bin, "-C", str(repo), "ls-files"],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0:
                for tracked in proc.stdout.splitlines():
                    parts = Path(tracked).parts
                    bad = [p for p in parts if p in VENDOR_IDE_DOTFOLDERS]
                    if bad:
                        tracked_violations.append(f"{repo.name}/{tracked} (contains {bad[0]})")

    assert not tracked_violations, "Tracked vendor IDE/agent dotfolder files detected:\n" + "\n".join(
        tracked_violations
    )
    assert not gitignore_violations, "Repository .gitignore hygiene violations:\n" + "\n".join(gitignore_violations)


@pytest.mark.unit
def test_zero_machine_local_paths_in_tracked_files() -> None:
    """Verify zero hardcoded machine-local home paths (/home/<user>/, /Users/<user>/) in docs and config."""
    files_to_scan: list[Path] = []

    for single in (REPO_ROOT / "AGENTS.md", REPO_ROOT / "Justfile"):
        if single.is_file():
            files_to_scan.append(single)

    for folder, suffixes in (
        (REPO_ROOT / "docs", {".md"}),
        (REPO_ROOT / "just", {".just"}),
        (REPO_ROOT / "scripts", {".py", ".sh"}),
    ):
        if folder.is_dir():
            for path in sorted(folder.rglob("*")):
                if path.is_file() and path.suffix in suffixes:
                    files_to_scan.append(path)

    if WORKSPACE_ROOT != Path("/") and WORKSPACE_ROOT.exists():
        root_agents = WORKSPACE_ROOT / "AGENTS.md"
        if root_agents.is_file():
            files_to_scan.append(root_agents)

        agent_repo = WORKSPACE_ROOT / "powercord-agent"
        if agent_repo.is_dir():
            scan_suffixes = {".md", ".py", ".json", ".sh", ".yml", ".yaml"}
            for path in sorted(agent_repo.rglob("*")):
                if any(p in path.parts for p in (".git", "__pycache__", ".venv", "tests")):
                    continue
                if path.is_file() and path.suffix in scan_suffixes:
                    files_to_scan.append(path)

    violations: list[tuple[str, int, str]] = []
    for file_path in files_to_scan:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(content.splitlines(), start=1):
            if MACHINE_LOCAL_PATH_RE.search(line):
                rel = (
                    str(file_path.relative_to(WORKSPACE_ROOT))
                    if WORKSPACE_ROOT in file_path.parents
                    else str(file_path.relative_to(REPO_ROOT))
                )
                violations.append((rel, lineno, line.strip()))

    assert not violations, f"Hardcoded machine-local home paths detected: {violations}"


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

    for py_file in _iter_files(CLIENT_ROOT, suffixes={".py"}):
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
    if EXTENSIONS_ROOT.exists():
        roots_to_scan.append(EXTENSIONS_ROOT)

    for root in roots_to_scan:
        for py_file in _iter_files(root, suffixes={".py"}, skip_dirs=DEFAULT_SKIP_DIRS | {"tests"}):
            if py_file.name == "alchemy.py":
                continue

            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"), filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "get_session":
                        rel_path = (
                            str(py_file.relative_to(REPO_ROOT))
                            if REPO_ROOT in py_file.parents
                            else str(py_file.relative_to(WORKSPACE_ROOT))
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
    if EXTENSIONS_ROOT.exists():
        roots_to_scan.append(EXTENSIONS_ROOT)

    for root in roots_to_scan:
        for py_file in _iter_files(root, suffixes={".py"}, skip_dirs=DEFAULT_SKIP_DIRS | {"tests"}):
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
                            else str(py_file.relative_to(WORKSPACE_ROOT))
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
    if EXTENSIONS_ROOT.exists():
        roots_to_scan.append(EXTENSIONS_ROOT)

    for root in roots_to_scan:
        for py_file in _iter_files(root, names={"models.py", "blueprint.py"}, skip_dirs=DEFAULT_SKIP_DIRS | {"tests"}):
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
                                else str(py_file.relative_to(WORKSPACE_ROOT))
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
    if EXTENSIONS_ROOT.exists():
        roots_to_scan.append(EXTENSIONS_ROOT)

    for root in roots_to_scan:
        for py_file in _iter_files(root, suffixes={".py"}, skip_dirs=DEFAULT_SKIP_DIRS | {"tests"}):
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
                                            else str(py_file.relative_to(WORKSPACE_ROOT))
                                        )
                                        violations.append((rel_path, node.name, sub.lineno))

    assert not violations, (
        f"Status edit helper discarding explicit view=None at {violations}.\n"
        "Use a sentinel default (e.g. _VIEW_UNSET = object()) and check 'if view is not _VIEW_UNSET:' "
        "so that explicitly passing view=None forwards view=None to Discord to clear interactive buttons."
    )


# ==============================================================================
# Invariant: Zero Automated PR Merges (Human Mk1 Authority)
# ==============================================================================


@pytest.mark.unit
def test_no_automated_pr_merges_in_scripts_or_recipes() -> None:
    """Verify that no Justfile, task runner, or script automates 'gh pr merge'.

    Per inv-branch-pr-review-gate, all PR merges into main require human Mk1 review.
    Automated tools and agents must never self-merge PRs.
    """
    violations = []
    roots_to_scan = [REPO_ROOT]
    if EXTENSIONS_ROOT.exists():
        roots_to_scan.append(EXTENSIONS_ROOT)

    for root in roots_to_scan:
        for file_path in _iter_files(
            root,
            suffixes={".sh", ".bash", ".py", ".just"},
            names={"Justfile", "Makefile"},
            skip_dirs=DEFAULT_SKIP_DIRS | {"backups", "tests"},
        ):
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"\bgh\s+pr\s+merge\b", content):
                violations.append(
                    str(
                        file_path.relative_to(REPO_ROOT)
                        if REPO_ROOT in file_path.parents
                        else file_path.relative_to(WORKSPACE_ROOT)
                    )
                )

    assert not violations, (
        f"Automated PR merge commands detected in: {violations}.\n"
        "Per inv-branch-pr-review-gate, 'gh pr merge' must never be automated. Merging requires human Mk1 review."
    )


# ==============================================================================
# Invariant: Container Filesystem Isolation Path Guards
# ==============================================================================


@pytest.mark.unit
def test_container_isolated_path_guards() -> None:
    """Verify that governance tests accessing WORKSPACE_ROOT guard against container environments.

    In isolated container builds (e.g. Cloud Build /workspace), REPO_ROOT.parent resolves to root '/',
    where sibling repositories and workspace AGENTS.md do not exist. Any test referencing
    WORKSPACE_ROOT or REPO_ROOT.parent must guard with an existence check and pytest.skip.
    """
    violations = []
    gov_dir = REPO_ROOT / "tests" / "governance"
    for py_file in gov_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if "WORKSPACE_ROOT" in content or "REPO_ROOT.parent" in content:
            if "pytest.skip" not in content:
                violations.append(py_file.name)

    assert not violations, (
        f"Governance test files referencing workspace root without pytest.skip container guards: {violations}.\n"
        "Guard workspace root accesses with 'if not ROOT_PATH.exists(): pytest.skip(...)' to maintain container parity."
    )


# ==============================================================================
# Invariant: Cold Boot Deployment Polling Margin (>=180s)
# ==============================================================================


@pytest.mark.unit
def test_prod_deploy_health_poll_timeout() -> None:
    """Verify that prod-deploy allows at least 180s for container startup.

    Cold VM reboots with remote Docker pulls and database migrations take 90-120s.
    Polling must allow at least 180s (>=60 loops x 3s) to prevent false-positive failures.
    """
    prod_just = REPO_ROOT / "just" / "prod.just"
    assert prod_just.exists(), "Missing just/prod.just"
    content = prod_just.read_text(encoding="utf-8")

    match = re.search(r"for\s+i\s+in\s+\{1\.\.(\d+)\};", content)
    assert match, "Could not find health check loop in just/prod.just"
    loop_count = int(match.group(1))
    assert loop_count >= 60, (
        f"prod-deploy health poll loop count is {loop_count} (<60 iterations). "
        "Must allow at least 180s (>=60 iterations at 3s interval) for cold container boot."
    )
