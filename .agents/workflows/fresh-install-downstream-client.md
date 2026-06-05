---
description: Seamlessly clones the Powercord Client framework into a new downstream deployment, installs required dependencies, and configures companion client-side extensions.
---

# Fresh Install Downstream Client Deployment

This workflow sets up a fresh downstream companion client deployment from the upstream client framework.

## Pre-requisite: Teardown
If updating an existing target directory, stop any running client processes, clean the environment, and wipe the target directory to avoid stale artifacts. We preserve any existing `.env` files in a temporary stash before wiping.
```bash
TARGET_DIR="/path/to/target-client"
TEMP_STASH="/path/to/stash-temp"

# Clean up dev environment and stop running processes
if [ -d "$TARGET_DIR" ]; then
    cd "$TARGET_DIR"
    if command -v just &>/dev/null; then
        just dev-clean
    fi
    cd ..
    
    # Stash client environment configs to preserve
    mkdir -p "$TEMP_STASH"
    find "$TARGET_DIR" -maxdepth 1 -type f -name ".env*" -exec cp {} "$TEMP_STASH/" \;
    
    rm -rf "$TARGET_DIR"
fi
```

## Steps

1. **Deploy Target:** Clone the upstream `powercord-client` repository into the target directory and disable upstream push.
```bash
UPSTREAM_DIR="/path/to/powercord-client"
TARGET_DIR="/path/to/target-client"
TEMP_STASH="/path/to/stash-temp"

git clone "$UPSTREAM_DIR" "$TARGET_DIR"
git -C "$TARGET_DIR" remote set-url --push origin DISABLED

# Restore preserved files
if [ -d "$TEMP_STASH" ]; then
    cp -r "$TEMP_STASH"/* "$TARGET_DIR/"
    rm -rf "$TEMP_STASH"
fi
```

2. **Dependency Seeding:** Install dependencies via Poetry to construct a clean virtual environment.
```bash
cd "/path/to/target-client"
just install
```

3. **Extension Injection:** Natively install domain-specific companion UI extensions from your local source ecosystem.
```bash
cd "/path/to/target-client"
just ext-install "../powercord-client-extensions/midi_library_client"
```

4. **Validation:** Launch the companion desktop application to verify it boots correctly with the extensions mounted.
```bash
cd "/path/to/target-client"
just run
```
