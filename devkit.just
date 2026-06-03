# Powercord Development Kit - Shared Recipes
# Import this file to access common development utilities.
# Usage: import 'devkit.just' (from powercord) or import? '../../powercord/devkit.just' (from extensions)

# Ensures the database service is running via Docker
[private]
_ensure-db:
    #!/usr/bin/env bash
    if ! ss -tln | grep -q ':5433 '; then
      echo "Starting local dev database container..."
      docker rm -f powercord-pg-dev 2>/dev/null || true
      docker run -d --name powercord-pg-dev -p 5433:5432 \
        -e POSTGRES_USER="$POWERCORD_POSTGRES_USER" \
        -e POSTGRES_PASSWORD="$POWERCORD_POSTGRES_PASSWORD" \
        -e POSTGRES_DB="$POWERCORD_POSTGRES_DB" \
        -v powercord_pg_dev_data:/var/lib/postgresql/data \
        postgres:15 >/dev/null
      echo "Waiting for database to be ready..."
      sleep 5
    fi

# Stops the standalone local dev database container if it's running
[private]
[no-exit-message]
_teardown-dev-db:
    #!/usr/bin/env bash
    docker rm -f powercord-pg-dev 2>/dev/null || true
