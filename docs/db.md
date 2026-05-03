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
