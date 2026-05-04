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

# Provision SSL
if [ -n "$POWERCORD_SSL_CERT" ] && [ -n "$POWERCORD_SSL_KEY" ]; then
    echo "Using provided SSL certificates from environment..."
    echo "$POWERCORD_SSL_CERT" > /etc/nginx/cert.pem
    echo "$POWERCORD_SSL_KEY" > /etc/nginx/key.pem
else
    echo "Generating temporary self-signed SSL certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/nginx/key.pem -out /etc/nginx/cert.pem -subj "/CN=proxy" || echo "Warning: openssl generation failed"
fi

if [ -f "/etc/nginx/cert.pem" ] && [ -f "/etc/nginx/key.pem" ]; then
    chmod 600 /etc/nginx/cert.pem /etc/nginx/key.pem
else
    echo "Warning: SSL certificates not found at /etc/nginx/cert.pem and key.pem. Nginx may fail to start."
fi

# Define PostgreSQL data directory. This path is what we'll mount as a volume.
PGDATA_DIR="/var/lib/postgresql/data/pgdata"

# Ensure app/data is persisted to the mounted volume
if [ ! -L "/app/data" ]; then
    echo "Symlinking /app/data to persistent storage..."
    mkdir -p /var/lib/postgresql/data/app_data
    # If /app/data exists and is a directory, copy its contents
    if [ -d "/app/data" ]; then
        cp -a /app/data/. /var/lib/postgresql/data/app_data/ || true
        rm -rf /app/data
    fi
    ln -s /var/lib/postgresql/data/app_data /app/data
fi

# Create the data directory and set permissions for the 'postgres' user
mkdir -p $PGDATA_DIR
chown -R postgres:postgres "$(dirname "$PGDATA_DIR")"
chmod 700 $PGDATA_DIR

# Check if the data directory is empty (first run)
if [ -z "$(ls -A $PGDATA_DIR 2>/dev/null)" ]; then
    echo "Initializing PostgreSQL database..."

    # Initialize the database cluster as the postgres user
    su - postgres -c "/usr/lib/postgresql/*/bin/initdb -D $PGDATA_DIR -E UTF8 --locale=C.UTF-8"

    # Configure postgres to allow external connections
    su - postgres -c "echo 'host all all 0.0.0.0/0 password' >> $PGDATA_DIR/pg_hba.conf"
    su - postgres -c "echo \"listen_addresses = '*'\" >> $PGDATA_DIR/postgresql.conf"
    su - postgres -c "echo \"max_wal_size = '2GB'\" >> $PGDATA_DIR/postgresql.conf"
    su - postgres -c "echo \"autovacuum = on\" >> $PGDATA_DIR/postgresql.conf"

    # Start PostgreSQL temporarily
    su - postgres -c "/usr/lib/postgresql/*/bin/pg_ctl -D $PGDATA_DIR -l /tmp/logfile start"
    sleep 5
    FRESH_INIT=true
else
    # Always start it temporarily for migrations if database is already initialized
    echo "Starting PostgreSQL temporarily for initialization checks..."
    
    # Apply Database Maintenance Tuning (Idempotent)
    grep -q "max_wal_size = '2GB'" $PGDATA_DIR/postgresql.conf || su - postgres -c "echo \"max_wal_size = '2GB'\" >> $PGDATA_DIR/postgresql.conf"
    grep -q "autovacuum = on" $PGDATA_DIR/postgresql.conf || su - postgres -c "echo \"autovacuum = on\" >> $PGDATA_DIR/postgresql.conf"

    rm -f $PGDATA_DIR/postmaster.pid
    su - postgres -c "/usr/lib/postgresql/*/bin/pg_ctl -D $PGDATA_DIR -l /tmp/logfile start"
    sleep 3
    FRESH_INIT=false
fi

# Ensure user and database exist (idempotent)
su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='${POWERCORD_POSTGRES_USER}'\" | grep -q 1 || psql -c \"CREATE USER ${POWERCORD_POSTGRES_USER} WITH PASSWORD '${POWERCORD_POSTGRES_PASSWORD}';\""
# Ensure the user has CREATEDB privileges so that test suites can provision test databases
su - postgres -c "psql -c \"ALTER USER ${POWERCORD_POSTGRES_USER} CREATEDB;\""
su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='${POWERCORD_POSTGRES_DB}'\" | grep -q 1 || psql -c \"CREATE DATABASE ${POWERCORD_POSTGRES_DB} OWNER ${POWERCORD_POSTGRES_USER} ENCODING 'UTF8';\""

# Run initialization scripts if they exist and this is a fresh database
if [ "$FRESH_INIT" = true ] && [ -f /db/init.sql ]; then
    echo "Running database initialization script /db/init.sql..."
    su - postgres -c "psql -v ON_ERROR_STOP=1 --dbname \"${POWERCORD_POSTGRES_DB}\" -f /db/init.sql"
fi

echo "Running Alembic migrations..."
alembic upgrade heads || echo "Warning: Migrations failed. Continuing..."
echo "Database initialized."

# Stop the temporary PostgreSQL server
su - postgres -c "/usr/lib/postgresql/*/bin/pg_ctl -D $PGDATA_DIR stop"
sleep 2

# Start all services via supervisord
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
