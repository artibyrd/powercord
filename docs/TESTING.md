# Powercord Testing Guide

## Running Tests

```bash
# Run all tests
just test

# Run only unit tests (fast, no external dependencies)
just test unit

# Run only integration tests (may need database or network)
just test integration

# Run tests with coverage report
just coverage
```

## Test Database Isolation

Tests run against an isolated PostgreSQL database named `powercord_test` —
they **never** touch the development database. This is enforced automatically
by the test configuration.

### How It Works

1. **Environment override**: `conftest.py` forces `POWERCORD_POSTGRES_DB=powercord_test`
   before any application modules are imported. This is a hard override, not a
   `setdefault`, so it takes effect even when `.env` sets a different value.

2. **Auto-provisioning**: A session-scoped fixture calls `ensure_test_database()`
   from `app/common/testing.py`. This connects to the PostgreSQL maintenance
   database and creates `powercord_test` if it doesn't exist. It also enables
   the `pg_trgm` extension so trigram search queries work identically to
   production.

3. **Clean slate per session**: The engine fixture drops and recreates all
   SQLModel tables at the start of each test session. This prevents stale data
   from prior runs from bleeding into assertions.

> [!IMPORTANT]
> The PostgreSQL Docker container **must be running** before tests execute.
> The `just test` recipe handles this automatically via the `_ensure-db`
> dependency, but if you run `pytest` directly, start the container first
> with `just _ensure-db`.

### Why Not SAVEPOINT Rollbacks?

A common pattern for test isolation is wrapping each test in a database
transaction with a SAVEPOINT and rolling back afterward. This doesn't work
in Powercord because some production code (e.g., `_delete_core_settings` in
`extension_hooks.py`) creates its own database sessions from the engine,
bypassing any SAVEPOINT-wrapped test session. Dropping and recreating
tables provides the same clean-slate guarantee without this limitation.

## Testing Standalone Extensions

Extensions distributed in separate repositories can run their own test suites independently using the `powercord` framework's centralized testing utility. 

To run extension tests via `just test` within the extension repository, ensure one of the following:
1. The extension repository is cloned natively as a sibling to the `powercord` core repository.
2. The `POWERCORD_PATH` environment variable is explicitly set and points to your local `powercord` core repository.

### Extension Credential Loading

Extension `conftest.py` files read the core repository's `.env` file to load
database credentials (`POWERCORD_DB_HOST`, `POWERCORD_POSTGRES_PASSWORD`,
etc.) that match the running Docker container. This is necessary because
extension Justfiles do not use `dotenv-load`. If the `.env` is missing (e.g.,
in CI), hardcoded fallback defaults are used.

## Test Organization

Tests are organized by type and live under `tests/`:

| Directory | Marker | Purpose |
|---|---|---|
| `tests/unit/` | `@pytest.mark.unit` | Fast, mocked tests for isolated logic |
| `tests/integration/` | `@pytest.mark.integration` | Tests requiring database or service deps |
| `tests/extensions/` | varies | Tests installed by extensions via `just ext-install` |

## Coverage Targets

**Overall target: ≥ 80%**

Individual module targets vary based on testability (see exclusions below).

## Coverage Exclusions

Some modules have low unit test coverage by design. This section documents
*why* and what alternative validation strategies exist.

### `app/db/db_tools.py` (~23% coverage)

**What's covered:** `get_or_create_internal_key()` — the only function with
pure database logic — is tested via `test_alchemy.py`.

**What's excluded:** `export_database()`, `import_database()`,
`_get_executable_path()`, `_is_docker_running()`, and the `__main__` CLI block.

**Why:** These functions shell out to `pg_dump`, `psql`, and
`docker compose`, and read platform-specific filesystem paths. Unit testing
would require mocking subprocess calls so heavily that the tests would only
verify the mocks, not real behavior.

**Validation strategy:** Manual verification via `just db-export` and
`just db-import`. Docker path is validated by `just run`.

---

### `app/common/extension_manager.py` (~56% coverage)

**What's covered:** `load_manifest()`, `get_installed_extensions()`,
`list_extensions()`, install/uninstall guard clauses, and internal-extension
prompt cancellation.

**What's excluded:** The core `install_extension()` and
`uninstall_extension()` workflows (file copy, `poetry add/remove`,
`alembic upgrade head`, interactive `input()` prompts).

**Why:** These functions orchestrate multiple subprocess calls
(`poetry add`, `alembic upgrade head`) and destructive filesystem operations
(`shutil.copytree`, `shutil.rmtree`). Heavy mocking would produce brittle
tests that don't validate the actual install/uninstall workflow.

**Validation strategy:** Manual testing via `just ext-install <path>` and
`just ext-uninstall <name>`. The extension lifecycle is also validated
end-to-end when building Docker images (`just run`).

---

### Key Testing Infrastructure

| Module | Purpose |
|---|---|
| `app/common/testing.py` | Shared test utilities: `TEST_DB_NAME`, `ensure_test_database()`, `setup_extension_test_env()` |
| `tests/conftest.py` | Core repo test configuration — env forcing, DB provisioning, engine/session fixtures |
