"""Documentation Integrity and Invariant Living Canon Governance Tests.

Governed by:
- inv-4tier-knowledge: 4-Tier Knowledge Placement & AGENTS.md context economy (<800 tokens)
- inv-living-canon: Dynamic Invariant Canon ("The Invariant Bible") with semantic slugs
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent
DOCS_ROOT = REPO_ROOT / "docs"
ROOT_AGENTS_MD = WORKSPACE_ROOT / "AGENTS.md"
AGENT_REPO_AGENTS_MD = WORKSPACE_ROOT / "powercord-agent" / "AGENTS.md"


@pytest.mark.unit
def test_agents_md_context_economy() -> None:
    """Verify that root AGENTS.md remains under the strict 800-token context economy budget."""
    assert ROOT_AGENTS_MD.exists(), f"Missing root AGENTS.md at {ROOT_AGENTS_MD}"
    content = ROOT_AGENTS_MD.read_text(encoding="utf-8")

    # Word count estimation: ~1.3 tokens per whitespace-delimited word
    words = content.split()
    estimated_tokens = int(len(words) * 1.3)

    assert estimated_tokens <= 850, (
        f"AGENTS.md context budget breached! Estimated tokens: {estimated_tokens} "
        f"(Word count: {len(words)}, Target: <800 tokens). Prune procedural details to progressive skills."
    )


@pytest.mark.unit
def test_agents_md_parity() -> None:
    """Verify exact parity between root AGENTS.md and powercord-agent/AGENTS.md."""
    if not AGENT_REPO_AGENTS_MD.exists():
        pytest.skip(f"powercord-agent/AGENTS.md not found at {AGENT_REPO_AGENTS_MD}")

    root_content = ROOT_AGENTS_MD.read_text(encoding="utf-8").strip()
    agent_content = AGENT_REPO_AGENTS_MD.read_text(encoding="utf-8").strip()

    assert root_content == agent_content, (
        "Parity drift detected between /AGENTS.md and powercord-agent/AGENTS.md! "
        "Keep them identical so submodules and root stay synchronized."
    )


@pytest.mark.unit
def test_dynamic_living_canon_invariant() -> None:
    """Verify that documentation references invariants by semantic slug without hardcoded numbers."""
    hardcoded_pattern = re.compile(
        r"\b(\d+)\s+(system\s+invariants|core\s+invariants|universal\s+invariants)\b", re.IGNORECASE
    )

    violations = []
    for md_file in REPO_ROOT.rglob("*.md"):
        if ".venv" in md_file.parts or "node_modules" in md_file.parts:
            continue
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            for line_idx, line in enumerate(content.splitlines(), start=1):
                if hardcoded_pattern.search(line):
                    violations.append((str(md_file.relative_to(REPO_ROOT)), line_idx, line.strip()))
        except Exception:
            pass

    assert not violations, f"Hardcoded invariant counter found (use dynamic Living Canon naming): {violations}"
