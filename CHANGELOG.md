# Changelog — Powercord Server Framework

All notable changes to the Powercord Server Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.3.0] - 2026-09-07

### 🎓 100% Architectural Ratchet Graduation & Sovereign Hardening
* **100% Zero Debt Graduation**: Completed the multi-milestone decoupling program for the 500 LOC Ceiling Law (`inv-500-loc-ceiling`). Active debt files in [`governance_ratchet.json`](tests/governance/governance_ratchet.json) dropped from 4 to **0**. Every source file across core, extensions, and downstream strictly satisfies $\le 500$ LOC:
  - `powercord/app/extensions/example/cog.py`: 1,138 LOC $\rightarrow$ 313 LOC facade + modular `cogs/` submodules (`counter.py`, `ping.py`, `greeter.py`, `help.py`, `views.py`).
  - `powercord-extensions/midi_library/cog.py`: 748 LOC $\rightarrow$ 113 LOC facade + `embeds.py`, `ui_views.py`, `command_handlers.py`.
  - `powercord-extensions/midi_library/routes.py`: 541 LOC $\rightarrow$ 70 LOC facade + `views/` subpackage (`gallery.py`, `modal.py`, `proxy.py`, `telemetry.py`).
  - `powercord/app/common/extension_manager.py`: 524 LOC $\rightarrow$ 462 LOC facade + `extension_manifest.py` (112 LOC) and `extension_alembic.py` (33 LOC).
* **Core Extension Directory Isolation Guard (`inv-source-isolation-no-ad-hoc-cp`)**:
  - Implemented `_is_core_repository()` guard in `app/common/extension_manager.py` that refuses direct extension installation into the core framework repository with a hard error directing operators to `powercord-downstream-server/`.
  - Updated `powercord/Justfile` so `ext-install` and `ext-uninstall` fail immediately if invoked in core, protecting repository boundaries.
  - Added `test_core_extensions_directory_isolation()` to `tests/governance/test_architecture_governance.py` to permanently fail if external extensions are detected in `app/extensions/`.
  - Purged untracked `app/extensions/honeypot/` from the core repository.
* **Core Dependency Cleanliness**:
  - Pruned 7 external extension dependencies (`pretty-midi`, `librosa`, `matplotlib`, `py7zr`, `rarfile`, `google-cloud-storage`, `cryptography`) from core `pyproject.toml`.
  - Reconciled `poetry.lock`, eliminating 1,889 lines of heavy transitive scientific and audio processing libraries (`scipy`, `numba`, `llvmlite`, `soundfile`, `soxr`) from the core framework.
* **Docker Hygiene & Disk Space Reclaim (`inv-single-vm-cost-ceiling`)**:
  - Added shared `docker-clean` recipe to `devkit.just` across core and downstream for pruning dangling images and build cache (`just docker-clean all=true`).
  - Reclaimed 7.76 GB of accumulated build cache.
* **Local Artifact Cleanliness**:
  - Pruned redundant root `.sql` dumps from `powercord/` (`bgml-data.sql`, `powercord-export.sql`, `bgml.dump`, `test_export.sql`), preserving the canonical versions in `/backup/`.
  - Enhanced `just dev-clean` to automatically purge temporary `*.log` and `.sql` test dumps.
  - Pruned stale tracking directories from the ecosystem root.

---

## [2.2.0] - 2026-09-06

### 🛡️ Security Auditor & Widget Engine Decoupling
* **Auditor Deconstruction**: Deconstructed the monolithic `widget.py` (2,783 LOC) in `app/extensions/utilities/` into modular single-responsibility components:
  - `security_engine/calculations.py`: Pure mathematical bitmask and permission ontology functions.
  - `security_engine/rules/`: Modular rule evaluators for channel exposure, ping abuse, role separation, and suggestive honeypot integration.
  - `security_engine/engine.py`: Core rule orchestration and state checksum caching.
  - `views/`: Reusable FastHTML components, modals, and formatters (`alerts_list.py`, `formatters.py`, `modals.py`).
  - `widgets/`: Focused card widgets (`overview.py`, `alerts.py`, `roles.py`, `channels.py`, `settings.py`, `permissions.py`, `overrides.py`, `auxiliary.py`).
  - `widget.py`: Compact 122 LOC registry and assembler facade.
* **Pure Function Ontology (`inv-compute-ontology`)**: Enforced `compute_*` prefix naming for pure mathematical and bitmask calculation functions across the codebase, backed by automated governance tests.

---

## [2.1.0] - 2026-09-05

### 🌐 FastHTML Web UI & Dashboard Deconstruction
* **Web UI Modularization**: Decoupled monolithic `app/main_ui.py` (1,398 LOC) into a compact 124 LOC application assembler and modular route handlers under `app/ui/routes/` (`admin.py`, `guild.py`, `public.py`, `admin_actions.py`, `admin_guard.py`).
* **Dashboard Engine Modularization**: Deconstructed monolithic `app/ui/dashboard.py` (2,084 LOC) into a cohesive `app/ui/dashboard/` subpackage (`layout.py`, `roles.py`, `settings.py`, `api_keys.py`, `grid.py`, `placement.py`).
* **Signature Preservation (`inv-fasthtml-card-signature`)**: Preserved the canonical `Card(title, content, **kwargs)` calling convention across all UI widget integrations.

---

## [2.0.0] - 2026-08-25

### 🧼 The Great Versioning Hygiene Reconciliation
* **Corrected True Baseline**: Officially reclaimed our rightful `v2.0.0` status, liberating the codebase from the humble `0.1.0` placeholder it had been wearing like an oversized thrift-store sweater while running full-fledged production workloads.
* **Invariant Governance**: Initialized Tier 0–2 Sovereign Invariant hierarchy, adopting shift-left governance test gates and 4-tier knowledge taxonomy cross-pollinated from the Credence ecosystem.
* **Single Fixed-Cost VM Sovereignty**: Permanently anchored architecture to a single GCP Compute Engine VM (`powercord-instance`), outlawing serverless autoscaling bill surprises for always-on Discord bot gateways.
* **Downstream Sandbox Isolation**: Formalized `powercord-downstream-server/` as the pre-commit integration testbed for multi-head Alembic migrations (`core`, `honey`, `midi`) and container verification.
* **Split-Stack Purity**: Hardened architectural boundaries between FastHTML/HTMX admin UI routes (`routes.py` / `widget.py`) and FastAPI REST sprockets (`sprocket.py`).
* **Branch & PR Review Lifecycle (`inv-branch-pr-review-gate`)**: Evolved commit governance to require dedicated feature branches (`just branch feat/<name>`), incremental local commits (`just commit <msg>`) strictly gated by `just check`, live downstream container verification (`http://localhost:5001/`), and GitHub pull request creation (`just pr-create`). Zero direct commits or pushes to `main`; human Mk1 review required for PR merges and release tagging.
