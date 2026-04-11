# Database Documentation

Powercord uses a modern database stack consisting of:
- **PostgreSQL**: Relational database engine.
- **SQLModel**: Python ORM (built on SQLAlchemy and Pydantic).
- **Alembic**: Database migration tool.

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

### 3. Run Tests
Execute the test suite, including database connectivity checks.
```bash
just db-test
```

### 4. Check Connection
Verify the application can connect to the database.
```bash
just db-connect
```

## Architecture

- **Models**: Defined in `app/db/models.py`.
- **Connection**: Managed in `app/common/alchemy.py`.
- **Migrations**: 
  - **Core Migrations**: Stored in the root `alembic/versions/`. This tracks essential framework tables (users, roles, API security models).
  - **Extension Migrations**: Stored fully independently inside each extension's structure (e.g., `app/extensions/<name>/alembic/versions/`). The system relies on dynamically parsing multibase branches during execution, maintaining 100% decoupled schema isolation where plugins can be dropped seamlessly without creating entangled histories.

## Core Tables

Powercord comes with built-in tables for managing its own state:
- **GuildExtensionSettings**: Tracks which gadgets (cogs, sprockets, widgets) are enabled for each guild.
- **WidgetSettings**: Stores configuration layout (order, column span, enabled state) for widgets on the public page.

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
