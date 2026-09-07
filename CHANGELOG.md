# Changelog — Powercord Server Framework

All notable changes to the Powercord Server Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-08-25

### 🧼 The Great Versioning Hygiene Reconciliation
* **Corrected True Baseline**: Officially reclaimed our rightful `v2.0.0` status, liberating the codebase from the humble `0.1.0` placeholder it had been wearing like an oversized thrift-store sweater while running full-fledged production workloads.
* **Invariant Governance**: Initialized Tier 0–2 Sovereign Invariant hierarchy, adopting shift-left governance test gates and 4-tier knowledge taxonomy cross-pollinated from the Credence ecosystem.
* **Single Fixed-Cost VM Sovereignty**: Permanently anchored architecture to a single GCP Compute Engine VM (`powercord-instance`), outlawing serverless autoscaling bill surprises for always-on Discord bot gateways.
* **Downstream Sandbox Isolation**: Formalized `powercord-downstream-server/` as the pre-commit integration testbed for multi-head Alembic migrations (`core`, `honey`, `midi`) and container verification.
* **Split-Stack Purity**: Hardened architectural boundaries between FastHTML/HTMX admin UI routes (`routes.py` / `widget.py`) and FastAPI REST sprockets (`sprocket.py`).
* **Branch & PR Review Lifecycle (`inv-branch-pr-review-gate`)**: Evolved commit governance to require dedicated feature branches (`just branch feat/<name>`), incremental local commits (`just commit <msg>`) strictly gated by `just check`, live downstream container verification (`http://localhost:5001/`), and GitHub pull request creation (`just pr-create`). Zero direct commits or pushes to `main`; human Mk1 review required for PR merges and release tagging.
