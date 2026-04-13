#!/bin/bash
set -e

# Load environment variables from Google Secret Manager explicitly before proceeding
if [ -f "/app/app/common/gsm_loader.py" ]; then
    echo "Loading environment variables from Secret Manager..."
    eval $(python -c "
import sys, os, shlex
sys.path.insert(0, '/app')
from app.common.gsm_loader import load_env
load_env()
for k, v in os.environ.items():
    if k.startswith('POWERCORD_'):
        print(f\"export {k}={shlex.quote(v)}\")
")
fi

export POWERCORD_DB_HOST="localhost:5432"

# Define PostgreSQL data directory. This path is what we'll mount as a volume.
PGDATA_DIR="/var/lib/postgresql/data/pgdata"

# Create the data directory and set permissions for the 'postgres' user
mkdir -p $PGDATA_DIR
chown -R postgres:postgres "$(dirname "$PGDATA_DIR")"
chmod 700 $PGDATA_DIR

# Check if the data directory is empty (first run)
if [ -z "$(ls -A $PGDATA_DIR 2>/dev/null)" ]; then
    echo "Initializing PostgreSQL database..."

    # Initialize the database cluster as the postgres user
    su - postgres -c "/usr/lib/postgresql/17/bin/initdb -D $PGDATA_DIR"

    # Start PostgreSQL temporarily to create the user and database
    su - postgres -c "/usr/lib/postgresql/17/bin/pg_ctl -D $PGDATA_DIR -l /tmp/logfile start"
    sleep 5

    # Create user and database from environment variables
    su - postgres -c "psql -c \"CREATE USER ${POWERCORD_POSTGRES_USER} WITH PASSWORD '${POWERCORD_POSTGRES_PASSWORD}';\""
    su - postgres -c "psql -c \"CREATE DATABASE ${POWERCORD_POSTGRES_DB} OWNER ${POWERCORD_POSTGRES_USER};\""

    # Configure postgres to allow external connections
    su - postgres -c "echo 'host all all 0.0.0.0/0 password' >> $PGDATA_DIR/pg_hba.conf"
    su - postgres -c "echo \"listen_addresses = '*'\" >> $PGDATA_DIR/postgresql.conf"

    # Run initialization scripts if they exist
    if [ -f /db/init.sql ]; then
        echo "Running database initialization script /db/init.sql..."
        su - postgres -c "psql -v ON_ERROR_STOP=1 --dbname \"${POWERCORD_POSTGRES_DB}\" -f /db/init.sql"
    fi
else
    # Always start it temporarily for migrations if database is already initialized
    echo "Starting PostgreSQL temporarily for Alembic migrations..."
    su - postgres -c "/usr/lib/postgresql/17/bin/pg_ctl -D $PGDATA_DIR -l /tmp/logfile start"
    sleep 3
fi

echo "Running Alembic migrations..."
alembic upgrade heads || echo "Warning: Migrations failed. Continuing..."
echo "Database initialized."

# Stop the temporary PostgreSQL server
su - postgres -c "/usr/lib/postgresql/17/bin/pg_ctl -D $PGDATA_DIR stop"
sleep 2

# Start all services via supervisord
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
