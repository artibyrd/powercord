# Powercord Server Guidelines (`powercord/`)

This repository contains the core Powercord backend server framework, FastAPI API routes, FastHTML dashboard views, Nextcord Discord bot integration, and Alembic database migrations.

---

## Core Server Invariants

1. **Split-Stack Separation**: Keep FastHTML routes (`app/ui/`) and FastAPI REST endpoints (`app/api/`) cleanly separated.
2. **Database Provisioning**: Dev database runs via `devkit.just` on port `5433`. Run `just _ensure-db` or `just test`.
3. **No Extension Pollution**: Never add extension-specific dependencies into core `pyproject.toml` or `poetry.lock`.
4. **Pytest Namespace**: Do not name FastAPI app instances `test_app` inside test modules to avoid pytest collection warnings.
5. **Pre-Commit Checks**: Always run `poetry run ruff check --fix . && poetry run ruff format .` and `poetry run pytest` before submitting changes for human review.
