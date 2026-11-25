# Release Lifecycle Policy for Powercord

Self-contained branching, integration verification, PR gating, multi-repo merge ordering, and production deployment policy for Powercord.

## Overrides

- **Local Downstream Integration Sandbox Instead of Cloud Previews (`inv-downstream-integration-testbed`, `inv-single-vm-cost-ceiling`)**:
  - Powercord runs on a single fixed-cost GCE VM (`powercord-instance`) with no cloud preview deployments.
  - `powercord-downstream-server/` is an ephemeral combined-testing workspace — treat its local branches and container volumes as disposable and rebuild freely from `powercord` `main`.
  - Before opening a PR, reconcile upstream changes into `powercord-downstream-server/` via git rebase and `just ext-install`, rebuild the Docker stack (`just rebuild-target`), verify multi-head migrations (`just db-upgrade && poetry run alembic heads`), and inspect the live web UI and bot on `http://localhost:5001/` (`inv-mk1-downstream-walkthrough-verification`).
- **Branch, Commit, and Human Mk1 Merge Authority (`inv-branch-pr-review-gate`)**:
  - Never push directly to `main`. Create semantic topic branches (`just branch feat/<topic>`) that describe the change — never couple a branch name to another repository's version.
  - Agents may run `just check` and `just commit "<msg>"` on feature branches and open PRs via `just pr-create`, but must never run `gh pr merge` or self-merge. Human Mk1 review and merge is mandatory.
- **Locked Downstream Production Origin & 5-Gate Deploy (`inv-downstream-deploy-origin`, `inv-no-unauthorized-gcp-deploy`, `inv-pre-deploy-qa-and-backup-gate`)**:
  - Submit production builds (`just gcp-build` / `just prod-deploy`) exclusively from `powercord-downstream-server/`, never from `powercord/`.
  - Production deploys require explicit human confirmation, local `:5001` UI sign-off, `just qa`, and a verified pre-deploy snapshot (`just prod-backup pre-deploy` with GCS archive and `backups/last_known_good.json`).

## Extensions

- **Topological Multi-Repo Merge Order**: When shipping coordinated changes across repositories, merge PRs strictly in dependency order after human review:
  1. `powercord-agent`
  2. `powercord`
  3. `powercord-extensions/*` (`honeypot`, `midi_library`)
  4. `powercord-client` and `powercord-client-extensions/*` (`midi_library_client`)
  5. `powercord-downstream-server` reconciliation, container rebuild, and `:5001` verification
- **Automated PR & Version-Bump Pre-Check (`powercord/scripts/validate_pr.py`)**:
  - `just pr-create` runs `scripts/validate_pr.py` before opening a PR to verify:
    1. Any `[vX.Y.Z]` (or pre-release `[vX.Y.Z-<tag>]`) tag in the PR title matches `pyproject.toml`.
    2. `pyproject.toml` version on `feat/*`, `feature/*`, `fix/*`, `hotfix/*`, and `release/*` branches is strictly greater than `origin/main:pyproject.toml` (`docs/*`, `ci/*`, and `chore/*` branches are exempt from version bumps).
    3. The latest `## [X.Y.Z]` heading in `CHANGELOG.md` matches `pyproject.toml`.
    4. Sibling `powercord-agent/plugin.json` (when present) carries valid aligned SemVer.
- **Strict SemVer Over Soft Roadmap Targets**: Version numbers in `ROADMAP.md` are soft planning targets, never reservations. Assign the next SemVer version after current `main` for whatever work ships next, and shift planned `ROADMAP.md` milestones outward to make room for prioritized interjected work.
- **Extension SemVer & Manifest Parity (`inv-manifest-version-parity`)**:
  - Pre-release extensions (`< 1.0.0`) remain decoupled from core releases until their `1.0.0` launch; published extensions (`>= 1.0.0`) bump versions independently when their own code changes.
  - External server extensions declare metadata and `[[tool.powercord.default_widgets]]` inside `pyproject.toml`; internal server extensions and client extensions use `extension.json`.
- **Cold-Boot Health Poll Margin & Docker Hygiene**:
  - Production health polling in `powercord/just/prod.just` must allow at least 180 seconds (`>= 60` iterations × 3s, enforced by `test_prod_deploy_health_poll_timeout`) to cover VM reset, image pull, and Alembic migrations.
  - Run `just docker-clean` after local downstream rebuilds and before submitting Cloud Builds. Keep `core.autocrlf=input` across all repos; never run `git reset --hard` on dirty upstream worktrees.

## Disabled / Not Applicable

- **Ephemeral Cloud Preview Environments**: Not applicable (no Cloud Run, Vercel, or Netlify preview URLs exist for Powercord).
- **Automated PR Merging**: Explicitly banned and enforced by `test_no_automated_pr_merges_in_scripts_or_recipes`.
