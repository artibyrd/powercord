# ---------------------------------------------------------------------------- #
#                                 DEV COMMANDS                                 #
# ---------------------------------------------------------------------------- #

# Install python dependencies
[group: "dev"]
install:
    poetry() { if [ "${1-}" = "lock" ] && [ "${2-}" = "--check" ]; then command poetry check --lock; else command poetry "$@"; fi; }; poetry lock --check || poetry lock
    poetry install

# Clean up temporary files
[group: "dev"]
dev-clean:
    @echo "Cleaning up..."
    find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -exec rm -rf {} +
    rm -f .coverage *.log app/logs/*.log test_*.sql
    [ -d .venv ] && rm -rf .venv || true
    @echo "Cleanup complete!"

# Kill any process listening on a given port (safe no-op if port is free)
[group: "dev"]
[no-exit-message]
[private]
_kill_port port:
    #!/usr/bin/env bash
    pids=$(lsof -ti :{{port}} 2>/dev/null)
    if [ -n "$pids" ]; then
      echo "$pids" | xargs kill -9 2>/dev/null || true
    fi

# Kill all dev server ports (5001=UI, 8000=API, 8001=Bot)
[group: "dev"]
[no-exit-message]
kill-dev:
    @just _kill_port 5001
    @just _kill_port 8000
    @just _kill_port 8001
    @echo Dev server processes killed.
alias kill := kill-dev

# Run the Powercord Discord bot
[group: "dev"]
[arg("debug", long, value="true")]
bot debug="false": install
    @just _kill_port 8001
    {{ if debug == "true" { "DEBUG=1 " } else { "" } }}poetry run python app/main_bot.py

# Run the FastAPI server
[group: "dev"]
[arg("debug", long, value="true")]
api debug="false": install
    @just _kill_port 8000
    poetry run uvicorn app.main_api:app --log-level {{ if debug == "true" { "debug" } else { "info" } }}

# Run the FastHTML frontend
[group: "dev"]
[arg("debug", long, value="true")]
ui debug="false": install
    @just _kill_port 5001
    {{ if debug == "true" { "DEBUG=1 " } else { "" } }}poetry run python app/main_ui.py

# Run Powercord stack locally.
[group: "dev"]
dev: install db-upgrade
    @just _dev_parallel

# Run Powercord stack locally in debug mode.
[group: "dev"]
dev-debug: install db-upgrade
    @just _dev_debug_parallel

[private]
[parallel]
_dev_parallel: _dev_message bot api ui

[private]
[parallel]
_dev_debug_parallel: (_dev_message "true") (bot "--debug") (api "--debug") (ui "--debug")

# Restart only the UI frontend (kills stale process first)
[group: "dev"]
[arg("debug", long, value="true")]
restart-ui debug="false":
    @just _kill_port 5001
    @just ui {{ if debug == "true" { "--debug" } else { "" } }}

# Run Powercord locally (containerized)
[group: "dev"]
run: _teardown-dev-db
    docker compose up --build

# Run Powercord locally (containerized) and reset database volume
[group: "dev"]
run-clean: _teardown-dev-db
    docker compose down -v
    docker compose up --build

# Clone the framework into a new downstream destination and disable upstream push
[group: "dev"]
init-target target_dir:
    #!/usr/bin/env bash
    echo "Cloning core framework downstream securely..."
    git clone . '{{target_dir}}'
    git -C '{{target_dir}}' remote set-url --push origin DISABLED
    echo "Target initialized. Pull upstream framework updates via 'git pull origin main' inside the target."

# Rebuild containerized environment with a fresh database volume
[group: "dev"]
rebuild-target:
    docker compose down -v
    docker compose up -d --build
    @echo "Target core rebuilt. You can now execute 'just ext-install' workflows safely."

# Single-command onboarding & health check
[group: "dev"]
ignite: install check
    @echo "Powercord environment ignited successfully."

# A recipe to show the startup message for the dev environment
[private]
_dev_message debug='false':
    @echo "Powercord is {{ if debug == "true" { "running in DEBUG mode" } else { "starting" } }}! Please wait ~1 minute for all services to start.  Use Ctrl+C to exit."

# Wait for containerized database to accept connections
[private]
_wait-for-compose-db:
    #!/usr/bin/env bash
    echo "Waiting for containerized database to become ready..."
    for i in {1..30}; do
      if docker compose exec -T app supervisorctl status postgres 2>/dev/null | grep -q "RUNNING" && docker compose exec -T app pg_isready -U postgres &>/dev/null; then
        echo "Database is ready!"
        exit 0
      fi
      echo "Database not ready yet (attempt $i/30)..."
      sleep 2
    done
    echo "Error: Database did not become ready." >&2
    exit 1
