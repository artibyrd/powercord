# ---------------------------------------------------------------------------- #
#                                 DB COMMANDS                                  #
# ---------------------------------------------------------------------------- #

# Upgrade the database to the latest version (see also: _wait-for-compose-db)
[group: "db"]
db-upgrade: _ensure-db
    poetry run python -c "from app.common.extension_manager import _update_alembic_ini; _update_alembic_ini()"
    poetry run alembic upgrade heads

# Create a new migration revision
[group: "db"]
db-revision message: _ensure-db
    poetry run python -c "from app.common.extension_manager import _update_alembic_ini; _update_alembic_ini()"
    poetry run alembic revision --autogenerate -m "{{message}}"

# Test connectivity to PostgreSQL
[group: "db"]
postgres: _ensure-db
    poetry run python app/common/alchemy.py
alias db-connect := postgres

# Resets Dashboard Admins (Clears the admin_users table)
[group: "db"]
reset-admins: _ensure-db
    poetry run python app/db/reset_dashboard_admins.py

# Add a dashboard admin. Usage: just add-admin <user_id> [--comment "Added via CLI"]
[group: "db"]
[arg("comment", long)]
add-admin user_id comment="Added via CLI": _ensure-db
    poetry run python app/db/add_admin.py {{user_id}} --comment "{{comment}}"

# Remove a dashboard admin. Usage: just remove-admin <user_id>
[group: "db"]
remove-admin user_id: _ensure-db
    poetry run python app/db/remove_admin.py {{user_id}}

# Add a third-party API key. Usage: just add-api-key <name> [--scopes '["global"]'] [--key <legacy_key>]
[group: "db"]
[arg("scopes", long)]
[arg("key", long)]
add-api-key name scopes='["global"]' key="": _ensure-db
    #!/usr/bin/env bash
    if [ -n "{{key}}" ]; then
      poetry run python app/db/manage_api_keys.py add "{{name}}" --scopes '{{scopes}}' --key "{{key}}"
    else
      poetry run python app/db/manage_api_keys.py add "{{name}}" --scopes '{{scopes}}'
    fi

# Revoke a third-party API key. Usage: just revoke-api-key <id>
[group: "db"]
revoke-api-key id: _ensure-db
    poetry run python app/db/manage_api_keys.py revoke {{id}}

# List all third-party API keys
[group: "db"]
list-api-keys: _ensure-db
    poetry run python app/db/manage_api_keys.py list

# Export the database to a file. Usage: just db-export [--file "powercord-export.sql"] [--migration]
[group: "db"]
[arg("file", long)]
[arg("migration", long, value="true")]  # BEGIN LEGACY: v2 data migration flag — see docs/LEGACY_V2_MIGRATION.md
db-export file="powercord-export.sql" migration="false": _ensure-db
    poetry run python app/db/db_tools.py export "{{file}}" {{ if migration == "true" { "--migration" } else { "" } }}

# Import the database from a file. Usage: just db-import <file>
[group: "db"]
db-import file: _ensure-db
    poetry run python app/db/db_tools.py import "{{file}}"

# Run an automated database backup
[group: "db"]
db-backup: _ensure-db
    poetry run python app/db/db_tools.py backup
