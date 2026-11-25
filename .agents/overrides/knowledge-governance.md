# Knowledge Governance Policy for Powercord

Self-contained knowledge placement, context-economy, and documentation governance guide for the Powercord ecosystem.

## Overrides

- **4-Tier Knowledge Taxonomy (`inv-4tier-knowledge`)**: Place every rule, procedure, check, and spec in its single proper tier:
  - **Tier 0 — Universal Core Invariants (`AGENTS.md`)**: High-signal, system-wide rules in Class α (Safety & Custody), Class β (Topology & Lifecycle), and Class γ (Interface & Governance). Must stay strictly under **800 tokens** (`int(len(words) * 1.33) <= 800`, enforced by `test_agents_md_context_economy`). Never put multi-line procedures, shell recipes, or setup guides here.
  - **Tier 1 — Progressive Skills & Overlays (`powercord-agent/skills/<skill>/SKILL.md` and `powercord-agent/overrides/<skill>.md`)**: On-demand domain skills with `references/` and `scripts/`, plus self-contained 3-section project overlays.
  - **Tier 2 — Shift-Left Automated Gates (`powercord/tests/governance/test_*.py` and `powercord-agent/scripts/lint_skills.py`)**: Fast (`~3–5s`) deterministic tests enforcing invariants before commit.
  - **Tier 3 — Blueprints, Guides & Release Ledgers (`powercord/docs/`, `CHANGELOG.md`, `ROADMAP.md`)**: Deep design docs, completed history, and forward-looking milestones.
- **Canonical `AGENTS.md` & Standalone Overlay Parity**:
  - `powercord-agent/rules/AGENTS.md` is the canonical source for umbrella root `AGENTS.md`; both files must stay byte-for-byte identical (enforced by `test_agents_md_parity`).
  - Core `powercord/.agents/overrides/` mirrors `powercord-agent/overrides/` via `just sync-overlays` so standalone clones of `powercord` have identical policy coverage (enforced by `test_standalone_skill_overlays_parity`).

## Extensions

- **Changelog vs. Roadmap Symmetry (`inv-changelog-session-parity`)**:
  - `CHANGELOG.md` is the permanent record of completed work and is updated every session.
  - `ROADMAP.md` is strictly forward-looking. Once a milestone ships, move its completed details into `CHANGELOG.md` and prune completed task checklists from `ROADMAP.md`.
- **Living Canon Semantic Slugs (`inv-living-canon`)**:
  - Reference invariants by semantic slug (such as `inv-branch-pr-review-gate`), never by hardcoded numbered counts (for example `"N core invariants"`). Enforced by `test_dynamic_living_canon_invariant`.
- **Plain-English Prose & Right-Shape Formatting Rule**:
  - Write docs, overlays, PR briefs, changelogs, implementation plans, and walkthroughs in clear, direct plain English.
  - Reserve Markdown tables for genuinely tabular data with short, uniform columns (for example PR merge order or version matrices); use headings and one-item-per-line bullet lists for narrative summaries, multi-file indices, and audit findings.
  - Avoid walls of inline `code-snippets` inside prose sentences; lead with what changed and why it matters, keeping backticks to the single path or command a point actually needs.
- **Knowledge Routing During `/learn` Retrospectives**:
  1. Never append procedural blobs or troubleshooting transcripts to `AGENTS.md`.
  2. Route subsystem procedures (Docker flags, Alembic steps, Flet quirks, GCP ops) into the owning skill's `references/` under `powercord-agent/skills/` or into `powercord-agent/overrides/`.
  3. Encode any architectural invariant that must never regress as a Tier 2 test in `powercord/tests/governance/`.
  4. Promote a rule to Tier 0 `AGENTS.md` only when every agent across every repository must know it before taking action.
- **Harness-Neutral Scratch & Plan Hygiene**:
  - Keep temporary scripts and logs outside tracked Git repositories (in the active harness session scratch directory or `/tmp/`); never leave untracked task runners or scratch files in repository or workspace roots (`inv-repo-bound-task-runners`).
  - Preserve the active master plan document; draft separate feature proposals in dedicated `<topic>.md` files.

## Disabled / Not Applicable

- **Retired `/remember` Command**: Superseded by `/learn`; remove any lingering references to `/remember`.
- **Eager Tier 1.5 `CODING_STANDARDS.md`**: Adopted lazily — do not pre-scaffold an empty `CODING_STANDARDS.md`; create it only if genuine unlintable repository-wide style calls emerge beyond Ruff and Mypy.
