# Justfile Guide

Powercord uses [`just`](https://just.systems/) as its command runner.
A `Justfile` defines short, memorable aliases for common development tasks
so you don't have to remember long shell commands.

## Do I need `just`?

**No.** Every recipe in a `Justfile` is a thin wrapper around standard
commands (`poetry run …`, `docker …`, `pytest …`). You can always read
the `Justfile` or the modular files in `just/`, copy the underlying
command, and run it directly.

`just` simply makes the experience faster and more consistent across the
team.

---

## Prerequisites

### 1. A POSIX-compatible shell (bash)

Powercord's justfiles are configured with `set shell := ["bash", "-cu"]`,
so **bash** must be available on your system.

| Platform | How to get bash |
|----------|-----------------|
| **Linux** | Most distributions ship with bash. Alpine uses ash/busybox by default — install bash via `apk add bash`. |
| **macOS** | macOS ships with zsh as the default shell, but bash is available. For a modern version: `brew install bash` ([Homebrew](https://brew.sh/)). |
| **Windows** | Use one of: **Git Bash** ([git-scm.com](https://git-scm.com/)) — ships with every Git for Windows install. **WSL / WSL2** ([install guide](https://learn.microsoft.com/en-us/windows/wsl/install)) — full Linux environment. **MSYS2 / MinGW** ([msys2.org](https://www.msys2.org/)) — lightweight POSIX layer. |

### 2. Install `just`

Follow the official installation instructions:
<https://just.systems/man/en/chapter_4.html>

After installation, verify with:
```bash
just --version
```

---

## Justfile structure

### Modular Root Justfile (`powercord/Justfile`)

The top-level `powercord/Justfile` is a lean (<120 LOC) entry point that
imports domain-focused modules from `just/`, shared dev utilities from
`devkit.just`, and optional internal extension recipes:

```just
import 'devkit.just'                              # shared dev & docker hygiene recipes
import 'just/dev.just'                            # local dev stack & containerized runs
import 'just/qa.just'                             # lint, format, typecheck, tests, agent-check, sync-overlays
import 'just/db.just'                             # Alembic migrations, backups, admins & API keys
import 'just/vcs.just'                            # multi-repo git status, branch, commit, pr-create, release
import 'just/prod.just'                           # Terraform & GCP production lifecycle (guarded)
import? 'app/extensions/example/extension.just'   # internal extension recipes (optional)
import? 'app/extensions/utilities/extension.just'
```

> [!NOTE]
> In `powercord-downstream-server/Justfile`, recipes from installed external extensions (`midi_library`, `honeypot`) are imported into the downstream environment.

Recipes are organized into groups across these modules:

| Module | Group(s) | Key Recipes | Purpose |
|--------|----------|-------------|---------|
| `just/dev.just` | `dev` | `install`, `dev`, `dev-debug`, `bot`, `api`, `ui`, `ignite`, `run` | Day-to-day local and containerized development |
| `just/qa.just` | `qa` | `check`, `lint`, `format`, `typecheck`, `test-gov`, `test`, `qa`, `agent-check`, `sync-overlays` | Hermetic code quality, governance, and skill overlay parity |
| `just/db.just` | `db` | `db-upgrade`, `db-revision`, `db-export`, `db-import`, `db-backup`, `add-admin`, `add-api-key` | Database migrations, backups, and access management |
| `just/vcs.just` | `vcs` | `status-all`, `branch`, `commit`, `pr-create`, `pr-status`, `release` | Version control, PR parity gating (`scripts/validate_pr.py`), and releases |
| `just/prod.just` | `deploy`, `prod` | `tf-init`, `tf-plan`, `tf-apply`, `gcp-build`, `prod-status`, `prod-backup`, `prod-deploy`, `prod-rollback`, `prod-db-restore` | Terraform and GCP production operations |
| `Justfile` | `extensions` | `ext-install`, `ext-uninstall`, `ext-list` | Extension lifecycle (run downstream) |

### Agent Governance & Skill Overlays (`agent-check`, `sync-overlays`)

Powercord works cleanly with any coding agent or IDE — and pairs optionally with the [`antigravity-customizations`](https://github.com/artibyrd/antigravity-customizations) companion suite via self-contained Markdown overlays under `.agents/overrides/<skill>.md`:

- **`just agent-check`** — Validates `powercord-agent` via `scripts/lint_skills.py` and its hook unit test suite, and conditionally runs `agy plugin validate --strict` only when `agy` is installed on `PATH` (zero hard lock-in).
- **`just sync-overlays`** — Mirrors canonical overlay files from sibling `../powercord-agent/overrides/*.md` into standalone `powercord/.agents/overrides/` so standalone clones of `powercord` stay synchronized (verified by `test_standalone_skill_overlays_parity`).
- **`just pr-create`** — Runs `python3 scripts/validate_pr.py` before pushing to verify SemVer bump progression over `origin/main`, PR title `[vX.Y.Z]` parity, `CHANGELOG.md` heading parity, and optional `powercord-agent/plugin.json` SemVer alignment.

### Shared Dev Kit (`powercord/devkit.just`)

Contains recipes shared across the framework and extensions:

- **`_ensure-db`** — Starts a local PostgreSQL Docker container on port
  5433 if one isn't already running.
- **`_teardown-dev-db`** — Stops and removes the dev database container.
- **`docker-clean [all="false"]`** — Prunes dangling Docker images and build cache
  to prevent build bloat on the sovereign VM (`inv-single-vm-cost-ceiling`).

Extensions import this file to reuse database provisioning without
duplicating logic.

### Extension Justfiles

Each extension has two justfile layers:

1. **`extension.just`** — Recipes that get imported into the downstream
   `powercord-downstream-server/Justfile` when the extension is installed (e.g.,
   `midi-migrate`, `midi-rescore`). These run in the context of the
   assembled server.

2. **`justfile`** (standalone) — A self-contained justfile for
   independent development within the extension's own repository. It
   includes its own `_ensure-db` that discovers `devkit.just` from the
   framework directory.

---

## Quick reference

```bash
just                  # List all available recipes
just check            # Fast hermetic pre-commit gate (<3s: lint + format + governance)
just typecheck        # Run mypy static type checks
just agent-check      # Validate powercord-agent plugin, skills, overlays, and hooks
just sync-overlays    # Sync .agents/overrides/*.md from sibling powercord-agent/
just dev              # Run Bot + API + UI locally
just dev-debug        # Run in debug mode
just qa               # Full quality check (lint + format + check + test)
just qa --fix         # Same, but auto-fix lint and formatting
just test             # Run unit tests only
just test --type all  # Run all tests (unit + integration)
just db-upgrade       # Apply database migrations
just install          # Install Python dependencies
just docker-clean     # Prune dangling Docker images and build cache (>24h)
just status-all       # Inspect git status across all 7 ecosystem repositories
just pr-create        # Validate PR version/CHANGELOG parity, push, and open PR
```

> [!NOTE]
> To install or manage external extensions, run `just ext-install <path>` inside `powercord-downstream-server/`. Direct installation into core `powercord/` is guarded and forbidden (`inv-source-isolation-no-ad-hoc-cp`).

Run `just --list` in any project directory to see all available recipes
and their descriptions.
