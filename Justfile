# use with https://just.systems

# ---------------------------------------------------------------------------- #
#                                 SETTINGS                                     #
# ---------------------------------------------------------------------------- #

set shell := ["cmd.exe", "/c"]
set export
set dotenv-load
set unstable

export PYTHONIOENCODING := "utf8"



# ---------------------------------------------------------------------------- #
#                                 CONSTANTS                                    #
# ---------------------------------------------------------------------------- #

gcp_project := `gcloud config get-value project`
gcp_bucket := gcp_project + "-tf-state"
gcp_default_image := "us-central1-docker.pkg.dev/" + gcp_project + "/powercord/powercord-app:latest"

# ---------------------------------------------------------------------------- #
#                                 HELPERS                                      #
# ---------------------------------------------------------------------------- #

# Default: List available just commands
default:
    @just --list --unsorted

# A recipe to show the startup message for the dev environment
[private]
_dev_message debug='false':
    @echo "Powercord is {{ if debug == "true" { "running in DEBUG mode" } else { "starting" } }}! Please wait ~1 minute for all services to start.  Use Ctrl+C to exit."

# Status reporter for nested jobs.
[private]
_run-with-status recipe *args:
    @echo ""
    @echo '{{ CYAN }}→ Running {{ recipe }}...{{ NORMAL }}'
    @just {{ recipe }} {{ args }}
    @echo '{{ GREEN }}✓ {{ recipe }} completed{{ NORMAL }}'
alias rws := _run-with-status

# Ensures the database service is running via Docker
[private]
_ensure-db:
    #!powershell
    $portInUse = Get-NetTCPConnection -LocalPort 5433 -State Listen -ErrorAction SilentlyContinue
    if (-not $portInUse) {
        Write-Host "Starting local dev database container..."
        docker rm -f powercord-pg-dev 2>$null | Out-Null
        docker run -d --name powercord-pg-dev -p 5433:5432 `
            -e POSTGRES_USER=$env:POWERCORD_POSTGRES_USER `
            -e POSTGRES_PASSWORD=$env:POWERCORD_POSTGRES_PASSWORD `
            -e POSTGRES_DB=$env:POWERCORD_POSTGRES_DB `
            -v powercord_pg_dev_data:/var/lib/postgresql/data `
            postgres:15 | Out-Null
        Write-Host "Waiting for database to be ready..."
        Start-Sleep -Seconds 5
    }


# ---------------------------------------------------------------------------- #
#                                 DEV COMMANDS                                 #
# ---------------------------------------------------------------------------- #

# Install python dependencies
[group: "dev"]
install:
    poetry install

# Clean up temporary files
[group: "dev"]
dev-clean:
    @echo "Cleaning up..."
    for /d /r . %d in (__pycache__ .pytest_cache .mypy_cache) do @if exist "%d" rd /s /q "%d"
    @if exist ".venv" rd /s /q ".venv"
    @echo "Cleanup complete!"

# Kill any process listening on a given port (safe no-op if port is free)
[group: "dev"]
[no-exit-message]
[private]
_kill_port port:
    #!powershell
    $connections = Get-NetTCPConnection -LocalPort {{port}} -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        $connections | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    }

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
bot debug="false":
    @just _kill_port 8001
    {{ if debug == "true" { "set DEBUG=1&& " } else { "" } }}poetry run python app/main_bot.py

# Run the FastAPI server
[group: "dev"]
[arg("debug", long, value="true")]
api debug="false":
    @just _kill_port 8000
    poetry run uvicorn app.main_api:app --log-level {{ if debug == "true" { "debug" } else { "info" } }}

# Run the FastHTML frontend
[group: "dev"]
[arg("debug", long, value="true")]
ui debug="false":
    @just _kill_port 5001
    {{ if debug == "true" { "set DEBUG=1&& " } else { "" } }}poetry run python app/main_ui.py

# Run Powercord stack locally.
[group: "dev"]
dev: db-upgrade
    @just _dev_parallel

# Run Powercord stack locally in debug mode.
[group: "dev"]
dev-debug: db-upgrade
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

# Run Powercord locally(containerized)
[group: "dev"]
run:
    docker compose up --build

# Run Powercord locally(containerized) and reset database volume
[group: "dev"]
run-clean:
    docker compose down -v
    docker compose up --build

# Clone the framework into a new downstream destination and disable upstream push
[group: "dev"]
init-target target_dir:
    #!powershell
    Write-Host "Cloning core framework downstream securely..."
    git clone . '{{target_dir}}'
    git -C '{{target_dir}}' remote set-url --push origin DISABLED
    Write-Host "Target initialized. Pull upstream framework updates via 'git pull origin main' inside the target."

# Rebuild containerized environment with a fresh database volume
[group: "dev"]
rebuild-target:
    docker compose down -v
    docker compose up -d --build
    @echo "Target core rebuilt. You can now execute 'just ext-install' workflows safely."

# ---------------------------------------------------------------------------- #
#                                 QA COMMANDS                                  #
# ---------------------------------------------------------------------------- #

# Quality Assurance. Usage: just qa [--fix]
[group: "qa"]
[arg("fix", long, value="true")]
qa fix="false": (lint fix) (format fix) check test

# Linting. Usage: just lint [--fix] (auto-fix issues)
[group: "qa"]
[arg("fix", long, value="true")]
lint fix="false":
    poetry run ruff check . {{ if fix == "true" { "--fix" } else { "" } }}
alias lc := lint

# Formatting. Usage: just format [--fix] (apply formatting, otherwise check-only)
[group: "qa"]
[arg("fix", long, value="true")]
format fix="false":
    poetry run ruff format . {{ if fix == "false" { "--check" } else { "" } }}

# Type Checking
[group: "qa"]
check:
    just _run-with-status _check
alias c := check

[private]
_check:
    poetry run mypy .

# Run tests. Usage: just test [--type unit|integration|all]
[group: "qa"]
[arg("type", long)]
test type="": _ensure-db
    just _run-with-status _test {{ if type != "" { "--type " + type } else { "" } }}
alias t := test

[private]
[arg("type", long)]
_test type="":
    #!powershell
    if ("{{type}}" -eq "all") { poetry run pytest tests }
    elseif ("{{type}}" -ne "") { poetry run pytest tests -m "{{type}}" }
    else { poetry run pytest tests -m "not integration" }
    exit $LASTEXITCODE

# Run tests and generate coverage report
[group: "qa"]
coverage: _ensure-db
    poetry run pytest --cov=app --cov-report=term-missing

# Run verification tests for the new dashboard features
[group: "qa"]
verify-dashboard: _ensure-db
    poetry run pytest tests/unit/test_internal_server.py tests/unit/test_ui_components.py tests/integration/test_admin_routes.py tests/integration/test_public_home.py

# ---------------------------------------------------------------------------- #
#                                 DB COMMANDS                                  #
# ---------------------------------------------------------------------------- #

# Upgrade the database to the latest version
[group: "db"]
db-upgrade: _ensure-db
    poetry run alembic upgrade head

# Create a new migration revision
[group: "db"]
db-revision message: _ensure-db
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

# Add a third-party API key. Usage: just add-api-key <name> [--scopes '["global"]']
[group: "db"]
[arg("scopes", long)]
add-api-key name scopes='["global"]': _ensure-db
    poetry run python app/db/manage_api_keys.py add {{name}} --scopes '{{scopes}}'

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
[arg("migration", long, value="true")]
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

# ---------------------------------------------------------------------------- #
#                                 EXTENSIONS                                   #
# ---------------------------------------------------------------------------- #

# Import extension justfiles (optional, only loaded when present)
import? 'app/extensions/midi_library/extension.just'
import? 'app/extensions/honeypot/extension.just'
import? 'app/extensions/example/extension.just'
import? 'app/extensions/utilities/extension.just'

# Install a Powercord extension from a local path. Usage: just ext-install <source_path>
[group: "extensions"]
ext-install source_path:
    poetry run python -m app.common.extension_manager install {{source_path}}

# Uninstall a Powercord extension by name. Usage: just ext-uninstall <name>
[group: "extensions"]
ext-uninstall name:
    poetry run python -m app.common.extension_manager uninstall {{name}}

# List all installed Powercord extensions
[group: "extensions"]
ext-list:
    poetry run python -m app.common.extension_manager list

# ---------------------------------------------------------------------------- #
#                                 DEPLOYMENT                                   #
# ---------------------------------------------------------------------------- #

# Run terraform init locally
[group: "deploy"]
tf-init:
    just _run-with-status _tf-init

[private]
_tf-init:
    cd terraform && terraform init -backend-config=bucket={{gcp_bucket}}

# Run terraform plan locally
[group: "deploy"]
[arg("docker_image", long)]
tf-plan docker_image=gcp_default_image:
    just _run-with-status _tf-plan {{docker_image}}

[private]
_tf-plan docker_image:
    cd terraform && terraform plan -var=project_id={{gcp_project}} -var=docker_image={{docker_image}}

# Apply infrastructure changes locally
[group: "deploy"]
[confirm("Are you sure you want to manually apply Terraform changes locally?")]
[arg("docker_image", long)]
tf-apply docker_image=gcp_default_image:
    cd terraform && terraform apply -var=project_id={{gcp_project}} -var=docker_image={{docker_image}}

# Destroy infrastructure
[group: "deploy"]
[confirm("Are you absolutely sure you want to DESTROY all Terraform infrastructure? This process cannot be reversed!")]
[arg("docker_image", long)]
tf-destroy docker_image=gcp_default_image:
    cd terraform && terraform destroy -var=project_id={{gcp_project}} -var=docker_image={{docker_image}}

# Build the Powercord Docker image and trigger the CI deployment pipeline
[group: "deploy"]
gcp-build:
    gcloud builds submit --config cloudbuild.yaml .
    @echo "Resetting the VM instance to pull the new image..."
    gcloud compute instances reset powercord-instance --zone us-central1-a

