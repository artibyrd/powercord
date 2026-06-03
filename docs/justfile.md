# Justfile Guide

Powercord uses [`just`](https://just.systems/) as its command runner.
A `Justfile` defines short, memorable aliases for common development tasks
so you don't have to remember long shell commands.

## Do I need `just`?

**No.** Every recipe in a `Justfile` is a thin wrapper around standard
commands (`poetry run …`, `docker …`, `pytest …`). You can always read
the `Justfile`, copy the underlying command, and run it directly.

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

### Main Justfile (`powercord/Justfile`)

The top-level Justfile lives in the `powercord/` directory and is the
primary entry point. It imports shared recipes and extension recipes:

```just
import 'devkit.just'                              # shared dev recipes
import? 'app/extensions/honeypot/extension.just'  # extension recipes (optional)
import? 'app/extensions/midi_library/extension.just'
```

Recipes are organized into groups:

| Group | Examples | Purpose |
|-------|----------|---------|
| `dev` | `install`, `dev`, `bot`, `api`, `ui` | Day-to-day development |
| `qa` | `lint`, `format`, `check`, `test`, `qa` | Code quality |
| `db` | `db-upgrade`, `db-revision`, `db-export` | Database management |
| `extensions` | `ext-install`, `ext-uninstall`, `ext-list` | Extension lifecycle |
| `deploy` | `tf-init`, `tf-plan`, `gcp-build` | Infrastructure / CI |

### Shared Dev Kit (`powercord/devkit.just`)

Contains recipes shared across the framework and extensions:

- **`_ensure-db`** — Starts a local PostgreSQL Docker container on port
  5433 if one isn't already running.
- **`_teardown-dev-db`** — Stops and removes the dev database container.

Extensions import this file to reuse database provisioning without
duplicating logic.

### Extension Justfiles

Each extension has two justfile layers:

1. **`extension.just`** — Recipes that get imported into the main
   `powercord/Justfile` when the extension is installed (e.g.,
   `midi-migrate`, `midi-rescore`). These run in the context of the
   framework.

2. **`justfile`** (standalone) — A self-contained justfile for
   independent development within the extension's own repository. It
   includes its own `_ensure-db` that discovers `devkit.just` from the
   framework directory.

---

## Quick reference

```bash
just                  # List all available recipes
just dev              # Run Bot + API + UI locally
just dev-debug        # Run in debug mode
just qa               # Full quality check (lint + format + typecheck + test)
just qa --fix         # Same, but auto-fix lint and formatting
just test             # Run unit tests only
just test --type all  # Run all tests (unit + integration)
just db-upgrade       # Apply database migrations
just install          # Install Python dependencies
just ext-install <p>  # Install an extension from a local path
```

Run `just --list` in any project directory to see all available recipes
and their descriptions.
