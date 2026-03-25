# Powercord — Fresh Setup Guide

How to clone, install extensions, and run Powercord from scratch.

## Prerequisites

| Tool | Install |
|------|---------|
| **Python 3.12** | [python.org](https://www.python.org/downloads/) |
| **Poetry** | [python-poetry.org](https://python-poetry.org/docs/#installation) |
| **Just** | [just.systems](https://just.systems/man/en/chapter_4.html) |
| **PostgreSQL** | [postgresql.org](https://www.postgresql.org/download/) |
| **Docker** | [docker.com](https://www.docker.com/) *(only needed for `just run`)* |

---

## 1. Clone the Repositories

```bash
# Clone the main Powercord framework
git clone <POWERCORD_REPO_URL> powercord
cd powercord

# Clone extensions into a sibling directory
cd ..
mkdir powercord-extensions
git clone <HONEYPOT_REPO_URL> powercord-extensions/honeypot
git clone <MIDI_LIBRARY_REPO_URL> powercord-extensions/midi_library
```

> [!NOTE]
> If cloning from local repos (e.g. on the same machine), use file paths:
> ```bash
> git clone "a:\Dev\Google\powercord" powercord
> git clone "a:\Dev\Google\powercord-extensions\honeypot" powercord-extensions/honeypot
> git clone "a:\Dev\Google\powercord-extensions\midi_library" powercord-extensions/midi_library
> ```

---

## 2. Configure Environment

```bash
cd powercord

# Create your .env file from the example (or manually)
cp .example.env .env
# Edit .env and fill in:
#   DISCORD_TOKEN       — your bot token from Discord Developer Portal
#   SESSION_KEY         — random string for web session encryption
#   DATABASE_URL        — your PostgreSQL connection string
#   (see .env for all available settings)
```

---

## 3. Install Framework Dependencies

```bash
just install
```

This runs `poetry install` and sets up pre-commit hooks.

---

## 4. Initialize the Database

```bash
# Run Alembic migrations to create all core tables
just db-upgrade

# Add yourself as an admin (required for dashboard access)
just add-admin <YOUR_DISCORD_USER_ID> "Initial Admin"
```

---

## 5. Install Extensions

Use `just ext-install` to install each external extension. This copies the
extension files into the framework, installs its Python dependencies, and
runs any database migrations it declares.

```bash
# Install the Honeypot extension
just ext-install ../powercord-extensions/honeypot

# Install the MIDI Library extension
just ext-install ../powercord-extensions/midi_library
```

Verify they're installed:
```bash
just ext-list
```

Expected output:
```
Name                 Version    Type       Description
────────────────────────────────────────────────────────────────────────────────
example              1.0.0      internal   Template and reference implementation...
honeypot             1.0.0      external   Automatic spammer-banning via monitor...
midi_library         1.0.0      external   MIDI file management with import, ana...
utilities            1.0.0      internal   Administrative tools for server analy...
```

> [!TIP]
> After installing extensions with Python dependencies (like `midi_library`),
> the poetry lock file in the framework is updated. Commit this if you want
> the dependency set to be reproducible.

---

## 6. Run Powercord

### Option A: Local Development (recommended for dev)
```bash
just dev
```
Starts the Bot, API, and UI processes directly on your machine.
- UI: http://localhost:5001
- API: http://localhost:8000

### Option B: Containerized (recommended for testing production behavior)
```bash
just run
```
Spins up the full stack in Docker containers.

> [!IMPORTANT]
> The Docker environment uses a **separate** PostgreSQL database.
> You'll need to run `just db-upgrade` and `just add-admin` inside the
> container on first run. Use `just db-export` / `just db-import` to
> migrate data between environments.

---

## 7. Legacy Migrations (Optional)

### 7.1. Import Legacy MIDI Data

If you have a legacy MIDI database SQL dump:

```bash
just midi-migrate <path_to_dump.sql>
```

This recipe is provided by the `midi_library` extension's own justfile
and is automatically available after installation.

### 7.2. Migrating Legacy API Keys (V2 to V3)

If you have an existing application using the older V2 of Powercord (e.g., `bards-guild-midi-project-2`), its legacy API keys are not automatically supported in the new V3 database. You will need to explicitly register the existing key string so that existing integrations won't break.

Execute the `manage_api_keys.py` script and pass the explicit legacy exact key using the `--key` flag:

```bash
# Example syntax using your exact legacy string
python app/db/manage_api_keys.py add "Legacy V2 App" --scopes '["global"]' --key "your-legacy-key-string-here"
```

This bypasses the internal secure generation and uses your specified key, ensuring existing API-consuming clients continue to work seamlessly.

---

## 8. Run QA

```bash
just qa        # lint + format check + type check + tests
just qa fix    # same, but auto-fix lint and formatting issues
```

---

## Uninstalling Extensions

```bash
just ext-uninstall honeypot
just ext-uninstall midi_library
```

> [!WARNING]
> Uninstalling removes the extension files and unique Python dependencies,
> but **does not** drop database tables. Clean those up manually if needed.

---

## Updating

### Updating the Framework

```bash
cd powercord
git pull origin main
just install          # Sync Python dependencies
just db-upgrade       # Apply any new database migrations
```

### Updating Extensions

External extensions are independent repos. To update one, pull the latest
version and re-install it over the existing copy:

```bash
# 1. Pull latest extension code
cd ../powercord-extensions/honeypot
git pull origin main

# 2. Re-install into the framework (overwrites the previous copy)
cd ../../powercord
just ext-uninstall honeypot
just ext-install ../powercord-extensions/honeypot
```

Repeat for each extension you want to update.

> [!TIP]
> After updating extensions, run `just db-upgrade` to apply any new
> migrations the extension may have added, and `just qa` to verify
> everything is still clean.

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `just install` | Install Python deps + pre-commit hooks |
| `just dev` | Run locally (Bot + API + UI) |
| `just run` | Run in Docker containers |
| `just qa fix` | Lint, format, type check, test |
| `just db-upgrade` | Apply database migrations |
| `just ext-install <path>` | Install an extension |
| `just ext-uninstall <name>` | Uninstall an extension |
| `just ext-list` | List installed extensions |
| `just db-export [file]` | Export database to SQL |
| `just db-import <file>` | Import database from SQL |
