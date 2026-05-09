# Database Documentation

Powercord uses a modern database stack consisting of:
- **PostgreSQL**: Relational database engine.
- **SQLModel**: Python ORM (built on SQLAlchemy and Pydantic).
- **Alembic**: Database migration tool.
- **pg_trgm**: PostgreSQL trigram extension for fuzzy text search.

## Build Setup

Dependencies are managed via Poetry.
- `sqlmodel`, `alembic`, `fastsql` are core dependencies.
- `pytest`, `pytest-asyncio` are dev/test dependencies.

## Common Tasks (Justfile)

### 1. Apply Migrations
Updates the database schema to match the code.
```bash
just db-upgrade
```

### 2. Create Migrations
After modifying `app/db/models.py`, generate a new migration script.
```bash
just db-revision "description_of_change"
```

### 3. Export / Import Data
```bash
just db-export [filename.sql]          # Export database to SQL
just db-import <filename.sql>          # Import database from SQL
just db-export <file> --migration      # INSERT-only dump (for pre-initialized targets)
```

### 4. Run Tests
Execute the test suite (runs against the isolated `powercord_test` database).
```bash
just test
```

See [TESTING.md](TESTING.md) for full testing documentation.

## Architecture

- **Models**: Defined in `app/db/models.py`.
- **Connection**: Managed in `app/common/alchemy.py`.
  - **Connection Pooling**: To optimize performance under high load, the SQLAlchemy connection pool can be tuned via optional environment variables. If omitted, they default to safe production values:
    - `POWERCORD_DB_POOL_SIZE` (default: 20) - The number of connections kept persistently open in the pool.
    - `POWERCORD_DB_MAX_OVERFLOW` (default: 10) - The maximum number of extra connections created during traffic spikes (over the `pool_size`).
    - `POWERCORD_DB_POOL_TIMEOUT` (default: 30) - Seconds to wait for an available connection before raising an error.
    - `POWERCORD_DB_POOL_RECYCLE` (default: 1800) - Seconds a connection can remain active before being recycled (prevents stale connections).
- **Search**: Trigram fuzzy search utilities in `app/db/search.py`.
- **Migrations**: 
  - **Core Migrations**: Stored in the root `alembic/versions/`. This tracks essential framework tables (users, roles, API security models) and PostgreSQL extensions (e.g., `pg_trgm`).
  - **Extension Migrations**: Stored fully independently inside each extension's structure (e.g., `app/extensions/<name>/alembic/versions/`). The system relies on dynamically parsing multibase branches during execution, maintaining 100% decoupled schema isolation where plugins can be dropped seamlessly without creating entangled histories.

## Core Tables

Powercord comes with built-in tables for managing its own state:
- **GuildExtensionSettings**: Tracks which gadgets (cogs, sprockets, widgets) are enabled for each guild.
- **WidgetSettings**: Stores configuration layout (order, column span, enabled state) for widgets on the public page.

## Trigram Search (`pg_trgm`)

Powercord provides a reusable fuzzy search utility backed by PostgreSQL's
`pg_trgm` extension. This enables typo-tolerant, similarity-ranked full-text
search across any string column.

### Enabling `pg_trgm`

The extension is enabled via the Alembic migration
`alembic/versions/a1b2c3d4e5f6_enable_pg_trgm.py`. This runs
`CREATE EXTENSION IF NOT EXISTS pg_trgm` and is safe to apply to databases
that already have it enabled.

### Using `build_trigram_query`

The `app/db/search.py` module provides a composable query builder:

```python
from sqlmodel import select
from app.db.search import build_trigram_query
from app.db.models import MyModel

# Basic usage — search across one or more columns
stmt = select(MyModel)
stmt = build_trigram_query(
    stmt,
    columns=[MyModel.name, MyModel.description],
    search_term="srch term",
)
results = session.exec(stmt).all()
```

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `stmt` | `SelectOfScalar` | required | Existing `select()` statement to augment |
| `columns` | `list[InstrumentedAttribute]` | required | String columns to search across |
| `search_term` | `str` | required | User's search query |
| `threshold` | `float` | `0.3` | Minimum similarity score (0.0–1.0) |
| `limit` | `int \| None` | `None` | Optional max results |

**Behavior:**
- Filters rows where **any** column meets the similarity threshold
- Orders results by the highest similarity score (best match first)
- Uses `func.greatest()` for multi-column ranking

### GIN Indexes

For optimal performance, extensions should create GIN trigram indexes on
searchable columns via their own Alembic migrations:

```python
from alembic import op

op.create_index(
    "ix_my_table_name_gin_trgm",
    "my_table",
    ["name"],
    postgresql_using="gin",
    postgresql_ops={"name": "gin_trgm_ops"},
)
```

### Configuring the Threshold

The default similarity threshold is `0.3` (PostgreSQL's own default). This
can be adjusted per-query by passing the `threshold` parameter, or globally
by changing `DEFAULT_SIMILARITY_THRESHOLD` in `app/db/search.py`.

Lower values return more results with weaker matches; higher values filter
more aggressively.

## Automated Backups

Powercord includes an automated backup system (`BackupService` in `app/db/db_tools.py`) that creates compressed daily database snapshots via APScheduler and prunes old backups automatically.

### How It Works

The backup pipeline has two layers:

1. **Application Layer**: The `BackupService` runs inside the Powercord process. An APScheduler cron job fires `create_daily_backup()` every day at **03:00 UTC**. This creates a `pg_dump` export, compresses it to `.sql.gz`, and removes backups older than **7 days**.
2. **Infrastructure Layer** *(GCP only)*: A host-level `systemd` timer (provisioned via Terraform) syncs the backup files from the persistent volume to a Google Cloud Storage bucket at **04:00 UTC** — one hour after creation to ensure the file is fully written.

### Backup Directory by Environment

The `BackupService` uses container detection (`/.dockerenv`) to determine the correct storage path. This ensures backups are always written to the appropriate location regardless of how Powercord is deployed:

| Environment | Detection | Backup Directory | Notes |
|---|---|---|---|
| **Bare-metal local dev** (`just dev`) | Not containerized | `<project_root>/backups/` | Backups stored alongside project files |
| **Docker Compose local dev** (`just run`) | Containerized | `/var/lib/postgresql/data/backups/` | Backups persist on the Docker volume |
| **Self-hosted Docker** (no GCP) | Containerized | `/var/lib/postgresql/data/backups/` | Backups persist on the mounted volume |
| **GCP production** | Containerized | `/var/lib/postgresql/data/backups/` | Backups synced to GCS by systemd timer |

### Manual Backup

You can trigger a backup manually at any time:
```bash
just db-backup
```
This runs the same `create_daily_backup()` logic used by the scheduler.

### Configuration

| Setting | Value | Location |
|---|---|---|
| Schedule | Daily at 03:00 UTC | `BackupService.start_scheduler()` |
| Retention | 7 days | `BackupService.RETENTION_DAYS` |
| Format | `.sql.gz` (gzip-compressed SQL) | `BackupService.create_daily_backup()` |
| GCS sync schedule | Daily at 04:00 UTC | `terraform/compute.tf` (systemd timer) |

> [!IMPORTANT]
> **Self-hosted users without GCS**: Your backups are stored only on the Docker volume. If you run `docker compose down -v`, both the database **and** the backups will be deleted. Consider configuring your own off-host sync (e.g., a cron job with `rsync`, `rclone`, or cloud CLI tools) to protect against volume loss.

> [!TIP]
> The `just db-export` command is a separate, on-demand export tool that writes to a user-specified file path. It is independent of the automated backup system and useful for creating migration dumps or ad-hoc snapshots.

## Usage in Code

To interact with the database, inject the session dependency:

```python
from app.common.alchemy import get_session
from app.db.models import MyModel
from sqlmodel import select

# In a function or route
session_gen = get_session()
session = next(session_gen)
try:
    results = session.exec(select(MyModel)).all()
finally:
    session.close()
```
