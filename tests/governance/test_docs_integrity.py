"""Documentation Integrity and Invariant Living Canon Governance Tests.

Governed by:
- inv-4tier-knowledge: 4-Tier Knowledge Placement & AGENTS.md context economy (<800 tokens)
- inv-living-canon: Dynamic Invariant Canon ("The Invariant Bible") with semantic slugs
- inv-repo-bound-task-runners: Repository-Bound Task Runners & Zero Untracked Root Files
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent
DOCS_ROOT = REPO_ROOT / "docs"
ROOT_AGENTS_MD = WORKSPACE_ROOT / "AGENTS.md"
AGENT_REPO_AGENTS_MD = WORKSPACE_ROOT / "powercord-agent" / "rules" / "AGENTS.md"
AGENT_OVERRIDES_DIR = WORKSPACE_ROOT / "powercord-agent" / "overrides"
STANDALONE_OVERRIDES_DIR = REPO_ROOT / ".agents" / "overrides"


@pytest.mark.unit
def test_agents_md_context_economy() -> None:
    """Verify that root AGENTS.md remains under the strict 800-token context economy budget."""
    if not ROOT_AGENTS_MD.exists():
        pytest.skip(f"Root AGENTS.md not found at {ROOT_AGENTS_MD} (isolated container build environment)")
    content = ROOT_AGENTS_MD.read_text(encoding="utf-8")

    # Word count estimation: ~1.33 tokens per whitespace-delimited word
    words = content.split()
    estimated_tokens = int(len(words) * 1.33)

    assert estimated_tokens <= 800, (
        f"AGENTS.md context budget breached! Estimated tokens: {estimated_tokens} "
        f"(Word count: {len(words)}, Target: <=800 tokens). Prune procedural details to progressive skills."
    )


@pytest.mark.unit
def test_agents_md_parity() -> None:
    """Verify exact parity between root AGENTS.md and powercord-agent/rules/AGENTS.md."""
    if not ROOT_AGENTS_MD.exists() or not AGENT_REPO_AGENTS_MD.exists():
        pytest.skip(f"powercord-agent/rules/AGENTS.md not found at {AGENT_REPO_AGENTS_MD}")

    root_content = ROOT_AGENTS_MD.read_text(encoding="utf-8").strip()
    agent_content = AGENT_REPO_AGENTS_MD.read_text(encoding="utf-8").strip()

    assert root_content == agent_content, (
        "Parity drift detected between /AGENTS.md and powercord-agent/rules/AGENTS.md! "
        "Keep them identical so the native plugin rule and workspace root stay synchronized."
    )


@pytest.mark.unit
def test_standalone_skill_overlays_parity() -> None:
    """Verify powercord/.agents/overrides/*.md stays synchronized with powercord-agent/overrides/*.md."""
    if not AGENT_OVERRIDES_DIR.exists():
        pytest.skip(f"Canonical overlays directory not found at {AGENT_OVERRIDES_DIR} (isolated container build)")

    assert STANDALONE_OVERRIDES_DIR.exists(), (
        f"Missing standalone overlays directory at {STANDALONE_OVERRIDES_DIR}. Run 'just sync-overlays'."
    )

    canonical_files = {p.name: p for p in sorted(AGENT_OVERRIDES_DIR.glob("*.md"))}
    standalone_files = {p.name: p for p in sorted(STANDALONE_OVERRIDES_DIR.glob("*.md"))}

    assert canonical_files, f"No overlay Markdown files found in {AGENT_OVERRIDES_DIR}"
    assert set(standalone_files.keys()) == set(canonical_files.keys()), (
        "Overlay file set drift between powercord-agent/overrides/ and powercord/.agents/overrides/! "
        f"Expected {sorted(canonical_files.keys())}, got {sorted(standalone_files.keys())}. "
        "Run 'just sync-overlays'."
    )

    drifted = []
    for name, canonical_path in canonical_files.items():
        if (
            canonical_path.read_text(encoding="utf-8").strip()
            != standalone_files[name].read_text(encoding="utf-8").strip()
        ):
            drifted.append(name)

    assert not drifted, f"Overlay content drift detected for {drifted}. Run 'just sync-overlays' to restore parity."


@pytest.mark.unit
def test_dynamic_living_canon_invariant() -> None:
    """Verify that documentation references invariants by semantic slug without hardcoded numbers."""
    hardcoded_pattern = re.compile(
        r"\b(\d+)\s+(system\s+invariants|core\s+invariants|universal\s+invariants)\b", re.IGNORECASE
    )

    violations = []
    skip_dirs = {".venv", "node_modules", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in skip_dirs)
        for fname in sorted(filenames):
            if not fname.endswith(".md"):
                continue
            md_file = Path(dirpath) / fname
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                for line_idx, line in enumerate(content.splitlines(), start=1):
                    if hardcoded_pattern.search(line):
                        violations.append((str(md_file.relative_to(REPO_ROOT)), line_idx, line.strip()))
            except Exception:
                pass

    assert not violations, f"Hardcoded invariant counter found (use dynamic Living Canon naming): {violations}"


@pytest.mark.unit
def test_workspace_root_cleanliness() -> None:
    """Verify that workspace root contains zero untracked task runners, scripts, or Justfiles."""
    if WORKSPACE_ROOT == Path("/") or not WORKSPACE_ROOT.exists():
        pytest.skip(f"Workspace root not applicable in container environment: {WORKSPACE_ROOT}")

    forbidden_patterns = ["Justfile", "*.just", "*.py", "*.sh", "*.bash"]
    violations = []
    for pattern in forbidden_patterns:
        for match in WORKSPACE_ROOT.glob(pattern):
            if match.is_file():
                violations.append(
                    f"Forbidden root file found: {match.name} (task runners must live inside repositories)"
                )

    assert not violations, "\n".join(violations)
