#!/bin/bash
set -e

# Define PostgreSQL data directory. This path is what we'll mount as a volume.
PGDATA_DIR="/var/lib/postgresql/data/pgdata"

# Check if the data directory is empty (first run)
if [ -z "$(ls -A $PGDATA_DIR)" ]; then
    echo "Initializing PostgreSQL database..."

    # Create the data directory and set permissions for the 'postgres' user
    mkdir -p $PGDATA_DIR
    chown -R postgres:postgres "$(dirname "$PGDATA_DIR")"
    chmod 700 $PGDATA_DIR

    # Initialize the database cluster as the postgres user
    # Note: The path to pg_ctl/initdb might change with the postgresql version
    su - postgres -c "/usr/lib/postgresql/17/bin/initdb -D $PGDATA_DIR"

    # Start PostgreSQL temporarily to create the user and database
    su - postgres -c "/usr/lib/postgresql/17/bin/pg_ctl -D $PGDATA_DIR -l /tmp/logfile start"

    # Wait a moment for PostgreSQL to be ready
    sleep 5

    # Create user and database from environment variables
    su - postgres -c "psql -c \"CREATE USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';\""
    su - postgres -c "psql -c \"CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};\""

    # Run initialization scripts if they exist
    if [ -f /db/init.sql ]; then
        echo "Running database initialization script /db/init.sql..."
        su - postgres -c "psql -v ON_ERROR_STOP=1 --dbname \"${POSTGRES_DB}\" -f /db/init.sql"
    fi

    echo "Running Alembic migrations..."
    alembic upgrade head

    echo "Database initialized."

    # Stop the temporary PostgreSQL server
    su - postgres -c "/usr/lib/postgresql/17/bin/pg_ctl -D $PGDATA_DIR stop"
fi

# Start all services via supervisord
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
