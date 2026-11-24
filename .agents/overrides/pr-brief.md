# Pull Request Brief Policy for Powercord

Self-contained PR description, verification evidence, and review handoff guide for the Powercord ecosystem.

## Overrides

- **Version-Tagged PR Titles**: For versioned `powercord` PRs (`feat/*`, `feature/*`, `release/*`), prefix the title with `[vX.Y.Z]` matching `pyproject.toml` and the latest `CHANGELOG.md` entry so `powercord/scripts/validate_pr.py` passes cleanly.
- **Local Downstream `:5001` Evidence Instead of Cloud Preview Links**: Powercord has no cloud preview URLs (`inv-single-vm-cost-ceiling`). Report local verification against `powercord-downstream-server/` on `http://localhost:5001/` alongside `just check`, `just typecheck`, and `just test --type unit` results.

## Extensions

- **Plain-English Lead**: Start every PR brief with 2–4 concise plain-English sentences explaining what changed, why it matters, and any migration or operator impact.
- **Multi-Repo Topology Table**: When a change spans more than one repository, include a compact table showing each repo, branch name, version bump, and topological merge order (`powercord-agent` → `powercord` → `powercord-extensions/*` → `powercord-client` & client extensions → `powercord-downstream-server`).
- **Governance & Migration Checklist**: Explicitly report:
  - Which Tier 0 invariant slugs apply to the diff (for example `inv-split-stack-isolation` or `inv-alembic-lineage-isolation`).
  - Whether Alembic migrations changed (`poetry run alembic heads` output).
  - Whether extension manifests (`extension.json` or `[tool.powercord]` in `pyproject.toml`) changed.
  - Plugin validation output (`just agent-check` / `agy plugin validate --strict powercord-agent/`) whenever `powercord-agent/` is modified.
- **Visual Verification for UI Changes**: For FastHTML/DaisyUI dashboard routes or widgets and Flet desktop client views, include before/after screenshots or a short visual verification note captured from local `http://localhost:5001/` or `just run`.

## Disabled / Not Applicable

- **Cloud Preview URLs & Canary Rollout Metrics**: Not applicable to Powercord's single-VM deployment model.
- **Self-Merge Sign-Off**: Never mark a PR as auto-merged or invoke `gh pr merge`; hand off clearly for Human Mk1 review (`inv-branch-pr-review-gate`).
