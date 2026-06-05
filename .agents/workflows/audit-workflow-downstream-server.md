---
description: Systematically audit the Powercord downstream server installation and all local development recipes to verify workspace health.
---

# Powercord Downstream Server Audit Workflow

This workflow guides human developers and Antigravity agents in verifying the health of the Powercord server downstream workspace and local developer recipes.

## Pre-requisites
1. A clean Docker environment.
2. Poetry and Python 3.12 installed on the host.

---

## Steps

### 1. Perform Downstream Installation Setup
Run the downstream installation setup workflow to establish a fresh environment:
```bash
# Call the downstream server setup workflow
/fresh-install-downstream-server
```
Verify that the `app` container starts up cleanly and prints `Application startup complete.` on `docker compose logs app`.

### 2. Verify Database Connectivity
Ensure that the host can connect directly to the containerized database:
```bash
cd powercord-downstream-server
just postgres
```
Expected output: `Connection successful: postgresql+pg8000://...`

### 3. Run QA Recipe Checks
Execute the code standards and testing commands to verify the code:
```bash
# Run linting
just lint

# Run formatting checks
just format

# Run mypy type checking
just check

# Run the test suite
just test

# Verify specific dashboard integrations
just verify-dashboard
```
Expected outcome: All lints pass, mypy prints `Success: no issues found`, and pytest runs successfully.

### 4. Verify Administrative & DB Utility Recipes
Run each DB utility tool to check state management:
```bash
# Test API key registration
just add-api-key "audit-key"
just list-api-keys
just revoke-api-key 1

# Test admin list manipulation
just add-admin 999999 --comment "Audit Admin"
just remove-admin 999999
just reset-admins

# Test export and backup utilities
just db-export --file "audit-db-export.sql"
just db-import "audit-db-export.sql"
just db-backup

# Clean up any generated files
rm audit-db-export.sql
rm backups/powercord_db_backup_*.sql.gz 2>/dev/null || true
```
Expected outcome: All SQL scripts execute and finish with exit code 0.

### 5. Verify Extension Recipes
Verify extension commands (using `midi_library` and `honeypot` extensions):
```bash
# Verify list command
just ext-list

# Run no-op tests
just honeypot-noop

# Run migration script
just midi-migrate "../powercord/bgml-data.sql"
```

### 6. Verify Host-based Dev Stack Startup
Test running the development servers on the host:
1. Stop the container stack: `docker compose down -v`
2. Start the standalone dev database: `just db-upgrade` (will run `_ensure-db`)
3. Launch `just api` in one background job and check startup logs.
4. Launch `just ui` in another background job and check startup logs.
5. Launch `just restart-ui` to verify port recycling.
6. Stop all dev tasks: `just kill-dev`
7. Clean up the standalone container: `docker rm -f powercord-pg-dev`

### 7. Restore Clean State
Bake-in extensions and restore the containerized daemon stack:
```bash
just rebuild-target
```
