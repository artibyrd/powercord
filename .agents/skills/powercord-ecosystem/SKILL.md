---
name: powercord-ecosystem
description: Use when making changes to the powercord server, client, or extensions, or when testing code in a locally installed project directory without contaminating source repositories.
---

# Powercord Ecosystem Architecture & Workflow

## Overview
Powercord consists of a centralized server framework, a Flet-based UI client, and their respective ecosystem of extensions. Development in the powercord ecosystem follows a strict separation of concerns between source repositories and active project installations to prevent cross-contamination.

## When to Use
- **Modifying Core Logic:** When altering the core `powercord` server or `powercord-client` source repositories.
- **Building Extensions:** When developing new integrations via `powercord-extensions` or `powercord-client-extensions`.
- **System Testing:** When you need to test changes across multiple repositories simultaneously to ensure integration fidelity.
- **Stand-up testing:** When bootstrapping a new project (e.g., `my-downstream-project`).

## Ecosystem Structure
The ecosystem is split across several source repositories with a standardized hierarchy. These are the absolute sources of truth for codebase configuration:

1. **`powercord`** (Server Source)
   - Core framework, FastAPI backend routes, Discord RBAC synchronization, database integrations, and GadgetInspector plugin systems.
2. **`powercord-extensions/*`** (Server Extensions)
   - Independent packages (like `honeypot` or `midi_library`) containing specialized Discord commands, DB models, and API endpoints which hook into the Server backend.
3. **`powercord-client`** (Client Source)
   - Core companion interface built with Flet, containing the application shell, settings configuration, and API HTTP communication layer to the Server.
4. **`powercord-client-extensions/*`** (Client Extensions)
   - UI views, custom Flet components, and client-side logic to mirror backend extension features (like `midi_library_client`).

## Tech Stack & Core Dependencies
The following are the current explicit, required dependency bounds for key components across the Powercord Ecosystem framework.

### Powercord (Server / Backend)
| Component | Minimum Version | Description |
|-----------|-----------------|-------------|
| Python | `>=3.12, <3.13` | Backend runtime environment |
| FastAPI | `^0.116.1` | Underlying REST API web framework |
| Nextcord | `^3.1.0` | Discord API wrapper (includes voice extras) |
| SQLModel | `^0.0.33` | Database ORM layer built on Pydantic & SQLAlchemy |
| python-fasthtml | `^0.12.21` | UI rendering utilities for server-side endpoints |
| Pytest | `^9.0.2` | Primary testing framework utilized by `just test` |

### Powercord-Client (UI / Frontend)
| Component | Minimum Version | Description |
|-----------|-----------------|-------------|
| Python | `>=3.11` | Client runtime environment |
| Flet | `>=0.82.0, <0.83.0`| Core UI library (Must adhere meticulously to v0.82+ async routing patterns) |
| HTTPX | `>=0.28.1, <0.29.0`| Synchronous and async HTTP client for server communication |
| Pydantic | `>=2.12.5, <3.0.0`| Data validation and serialization for UI models |

## Development Workflow: Source Isolation

**CRITICAL RULE:** Never run, test, instantiate `.env` files, or build databases directly within the source repository directories.

Instead, execute the following explicit workflow to test changes using a specific, self-contained project context:

### 1. Edit the Source Repositories
Author and commit your code changes inside the independent source repositories (e.g., `Google/powercord`, `Google/powercord-extensions/midi_library`). The code here MUST remain generic and framework-oriented. Do not put implementation-specific or secrets data here.

### 2. Stand Up a "Fresh Install" Project Directory
Create or use a distinct implementation repository (such as `my-downstream-project`) to act as the staging testbed. This operational directory acts as a dedicated instance of your framework for validation purposes.

### 3. Initialize the Project Environment
Powercord utilizes `poetry` tightly integrated with `just` for testbed lifecycle execution. Within your test project directory, execute:

```bash
just dev-clean  # Purges any existing .venv or cache state to prevent staleness
just install    # Executes `poetry install` generating a clean .venv mapped to base dependencies
```

To integrate an extension from your local source ecosystem seamlessly into the testbed (`.venv`), you must use the `ext-install` command:

```bash
just ext-install ../powercord-extensions/midi_library
# Ensure this command is rerun to refresh local pointers if substantial structural updates happen
```

### 4. Test within the Project Environment
Run your system integration tests and launch via standard `justfile` pipelines exclusively from the project directory.

```bash
cd path/to/project/directory
just dev
```

## Quick Reference
| Target Modification | Target Action / Repository |
| --- | --- |
| Altering core SQL backend schema | Modify the `powercord` source repository |
| Crafting an integration-specific module | Construct within `powercord-extensions/[feature]` |
| Adding a UI dashboard view | Construct within `powercord-client-extensions/[feature]` |
| Validating overall functionality | `cd /project-dir` followed by `just ext-install ../path` |
| Establishing deployment environment vars| Create `.env` exclusively in the staging project directory |

## Shared Development Recipes (`devkit.just`)

The `powercord/devkit.just` module centralizes reusable `just` recipes that extensions and the framework itself depend on during development. This eliminates duplication across repositories.

### What It Provides
| Recipe | Purpose |
| --- | --- |
| `_ensure-db` | Starts a local PostgreSQL 15 Docker container on port 5433 if one isn't already running. Uses `ss` for port detection and `pg_isready` for readiness polling. |
| `_teardown-dev-db` | Stops and removes the `powercord-pg-dev` container. |

### How Extensions Resolve It

Extensions include a self-resolving `_ensure-db` recipe that discovers and delegates to `devkit.just` at runtime:

```just
[private]
_ensure-db:
    #!/usr/bin/env bash
    pc_path="${POWERCORD_PATH:-../../powercord}"
    devkit="$pc_path/devkit.just"
    if [ -f "$devkit" ]; then
      just --justfile "$devkit" _ensure-db
    else
      echo "[devkit] powercord/devkit.just not found - skipping DB provisioning"
    fi
```

**Resolution order:**
1. `POWERCORD_PATH` environment variable (explicit override — same var used by `conftest.py`)
2. `../../powercord` relative path (standard sibling layout)
3. Warning message if neither resolves (CI pipelines, non-standard layouts)

### When to Use vs. When It's Skipped

| Context | `_ensure-db` Resolution |
| --- | --- |
| Extension repo cloned next to `powercord/` | ✅ Devkit found via relative path — Docker DB auto-provisioned |
| Extension repo in non-standard location | ✅ Set `POWERCORD_PATH` to resolve |
| Inside a downstream project (e.g., `my-downstream-project`) | ✅ Project-level Justfile has its own `_ensure-db` via `import 'powercord/devkit.just'` |
| CI pipelines / no powercord checkout | ⚠️ Warning printed — CI manages its own DB services |

## Agent-Specific Notes

- **`install` is a prerequisite:** The `qa`, `dev`, `dev-debug`, `bot`, `api`, and `ui` recipes automatically run `poetry install` first. No manual setup step is needed.
- **`[confirm]` prompts:** The `tf-apply` and `tf-destroy` recipes use interactive confirmation prompts that will fail in non-interactive agent shells. Use `just --yes tf-apply` to bypass.
- **GCP project:** Deploy recipes (`tf-*`, `gcp-build`) require `POWERCORD_GCP_PROJECT` to be set (loaded from `.env` via `dotenv-load`). They will error clearly if it is missing.

## Common Failure Patterns to Avoid
- **Environment Shadowing / Contamination:** Generating `.env` files or stray compilation artifacts directly inside the `powercord` source directory. These must solely exist inside a fresh project directory.
- **Dependency Desync:** Using manual pip installations which override production lockfiles. Always use `just ext-install` to guarantee stable local editable references for testbed evaluation.
- **Discord Client Caching (Phantom Bugs):** If slash commands are not appearing in the Discord server after a restart or deployment, **investigate client caching problems BEFORE writing diagnostic tests or debugging code**. Discord clients heavily cache slash commands. Always advise the user to force-refresh their Discord client (e.g., `Ctrl+R`) or check on another device before assuming the bot's command registration failed.
- **Missing `devkit.just` Warnings:** If an extension's `just test` prints a yellow `[devkit]` warning, set `POWERCORD_PATH` or ensure the standard sibling layout. Without DB provisioning, tests will fail with database connection errors.

