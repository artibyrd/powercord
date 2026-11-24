# Domain Modeling Policy for Powercord

Self-contained ubiquitous language reference and ADR placement guide for the Powercord ecosystem.

## Overrides

- **Lazy `GLOSSARY.md` & `docs/adr/` Adoption**: Do not pre-scaffold an empty `GLOSSARY.md` or empty `docs/adr/` directory. Create `powercord/docs/adr/NNNN-<slug>.md` lazily only when an architectural decision is genuinely hard to reverse (such as changing data topology, authentication boundaries, or multi-repo contracts).
- **Authoritative Existing Blueprints**: Treat `powercord/docs/` as the primary technical reference rather than duplicating specifications across parallel glossary files:
  - `powercord/docs/extensions.md` — Extension architecture, manifests, and widget namespaces.
  - `powercord/docs/api_developer_guide.md` & `powercord/docs/api.md` — FastAPI sprockets and scoped REST APIs.
  - `powercord/docs/db.md` — SQLModel schemas and isolated multi-head Alembic migrations.
  - `powercord/docs/cogs.md` & `powercord/docs/INTENTS.md` — Nextcord bot cogs and Discord Gateway intents.
  - `powercord/docs/SECURITY_AUDITOR.md` & `powercord/docs/utilities.md` — Discord RBAC rule engine and auditing.
  - `powercord/docs/discovery.md` — Dynamic gadget and extension discovery.

## Extensions

- **Canonical Powercord Ubiquitous Language**: Use these exact domain terms consistently across code, tests, docs, and PRs:
  - **Cog (`cog.py`)**: A Nextcord Discord bot module implementing slash commands, event listeners, and Discord interactions.
  - **Sprocket (`sprocket.py`)**: A FastAPI REST JSON router exposing typed Pydantic endpoints gated by `api_scope_required(extension, level)` for companion clients and API integrations.
  - **Widget (`widget.py`)**: A FastHTML + DaisyUI server-rendered dashboard component scoped strictly by function name prefix (`admin_`, `guild_admin_`, or public).
  - **Route (`routes.py`)**: A full-page FastHTML UI view returning FT components for HTMX-driven web pages.
  - **Action (`actions.py`)**: A scheduled background job (interval or cron) registered by an extension.
  - **Blueprint (`blueprint.py`)**: Extension-owned SQLModel database models, pure `compute_*` business logic, and data-access helpers.
  - **Extension**: A modular feature unit packaged either as an internal built-in (`powercord/app/extensions/{custom_content,example,utilities}` with `extension.json`), an external server package (`powercord-extensions/<name>` with `[tool.powercord]` in `pyproject.toml`), or a companion client package (`powercord-client-extensions/<name>` with `extension.json`).
  - **Downstream (`powercord-downstream-server/`, `powercord-downstream-client/`)**: Isolated local staging assembly where upstream core and external extensions are combined, containerized, and verified on `http://localhost:5001/` before PRs or production builds.
  - **MCI (MIDI Craftsmanship Index)**: The `midi_library` extension's composite musical quality index computed via pure `compute_*` scoring functions over parsed MIDI features.
  - **Security Auditor**: The built-in `utilities` rule engine evaluating Discord RBAC bitmasks (always gated on View Channel `1 << 10` and category overwrite inheritance) with database-checksum-keyed evaluation caches.

## Disabled / Not Applicable

- **Multi-Tenant Sharding & Distributed Event Buses**: Not applicable — Powercord models a single-instance PostgreSQL database with isolated per-extension Alembic migration heads (`inv-alembic-lineage-isolation`) and per-guild cleanup via `delete_guild_data` (`inv-guild-data-lifecycle`).
