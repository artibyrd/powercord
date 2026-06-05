---
description: Seamlessly clones the Powercord framework into a new downstream deployment, provisions the container environment, and natively configures core extensions.
---

# Fresh Install Downstream Deployment

This workflow sets up a fresh downstream deployment from the upstream core framework. 

## Pre-requisite: Teardown
If updating an existing target directory, completely wipe it first to avoid artifacts. We preserve `.sql`, `.dump`, and `.env` files in a temporary stash before wiping.
```bash
TARGET_DIR="/path/to/target-project"
TEMP_STASH="/path/to/stash-temp"

# Stop running containers and destroy the old database volume
if [ -d "$TARGET_DIR" ]; then
    cd "$TARGET_DIR"
    if [ -f "docker-compose.yml" ]; then 
        docker compose down -v 
    fi
    cd ..
    
    # Stash files to preserve
    mkdir -p "$TEMP_STASH"
    find "$TARGET_DIR" -maxdepth 1 -type f \( -name "*.sql" -o -name "*.dump" -o -name ".env*" \) -exec cp {} "$TEMP_STASH/" \;
    
    rm -rf "$TARGET_DIR"
fi
```

## Steps

1. **Deploy Target:** Navigate to the upstream `powercord` repository and execute `init-target`. This safely creates a clone and disables upstream pushes to protect the core framework.
```bash
UPSTREAM_DIR="/path/to/powercord"
TARGET_DIR="/path/to/target-project"
TEMP_STASH="/path/to/stash-temp"

cd "$UPSTREAM_DIR"
just init-target "$TARGET_DIR"

# Restore preserved files
if [ -d "$TEMP_STASH" ]; then
    cp -r "$TEMP_STASH"/* "$TARGET_DIR/"
    rm -rf "$TEMP_STASH"
fi
```

2. **Migrate Secrets:** Copy your internal security profiles.
```bash
UPSTREAM_DIR="/path/to/powercord"
TARGET_DIR="/path/to/target-project"

if [ ! -f "$TARGET_DIR/.env" ]; then
    cp "$UPSTREAM_DIR/.env" "$TARGET_DIR/.env"
fi
if [ ! -f "$TARGET_DIR/.env.prod" ]; then
    cp "$UPSTREAM_DIR/.env.prod" "$TARGET_DIR/.env.prod"
fi
```

3. **Dependency Seeding:** Install Python requirements in the new target to generate the `.venv`.
```bash
cd "/path/to/target-project"
just install
```

4. **Containerization:** Spin up the base container and database. Wait until PostgreSQL is fully responsive.
```bash
cd "/path/to/target-project"
just rebuild-target
```

5. **Extension Injection:** Natively install domain-specific endpoints and capabilities.
```bash
cd "/path/to/target-project"
just ext-install "../powercord-extensions/midi_library"
just ext-install "../powercord-extensions/honeypot"
```

6. **Image Bake-in:** Execute a final rebuild to inject extension artifacts into the persistent Docker image.
```bash
cd "/path/to/target-project"
just rebuild-target
```

7. **Database Restore:** If a `powercord-export.sql` file was preserved, import it to restore the database state.
```bash
cd "/path/to/target-project"
if [ -f "powercord-export.sql" ]; then
    just db-import "powercord-export.sql"
fi
```

8. **Validation:** Ensure clean startup via `docker compose logs`. Verify that Uvicorn logs `Application startup complete.` and extension components mounted natively.
```bash
cd "/path/to/target-project"
docker compose logs --tail 30 app
```