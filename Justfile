# use with https://just.systems
set shell := ["cmd.exe", "/c"]
set export


# List available just commands
default:
    @just --list --unsorted


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


# Quality Assurance. Usage: just qa [fix] (pass "fix" to auto-fix lint and format issues)
[group: "qa"]
qa fix="": (lint fix) (format fix) check test


# Linting. Usage: just lint [fix] (pass "fix" to auto-fix issues)
[group: "qa"]
lint fix="":
    poetry run ruff check . {{ if fix == "fix" { "--fix" } else { "" } }}


# Formatting. Usage: just format [fix] (pass "fix" to apply formatting, otherwise check-only)
[group: "qa"]
format fix="":
    poetry run ruff format . {{ if fix != "fix" { "--check" } else { "" } }}


# Type Checking
[group: "qa"]
check:
    poetry run mypy .


# Kill any process listening on a given port (safe no-op if port is free)
[group: "dev"]
[no-exit-message]
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
bot debug='false':
    @just _kill_port 8001
    {{ if debug == "debug" { "set DEBUG=1&& " } else { "" } }}poetry run python app/main_bot.py


# Run the FastAPI server
[group: "dev"]
api debug='false':
    @just _kill_port 8000
    poetry run uvicorn app.main_api:app --log-level {{ if debug == "debug" { "debug" } else { "info" } }}


# Run the FastHTML frontend
[group: "dev"]
ui debug='false':
    @just _kill_port 5001
    {{ if debug == "debug" { "set DEBUG=1&& " } else { "" } }}poetry run python app/main_ui.py


# Upgrade the database to the latest version
[group: "db"]
db-upgrade:
    poetry run alembic upgrade head


# Create a new migration revision
[group: "db"]
db-revision message:
    poetry run alembic revision --autogenerate -m "{{message}}"


# Run tests. Usage: just test [type] (type: unit, integration, or empty for all)
[group: "qa"]
test type="":
    poetry run pytest tests {{ if type != "" { "-m " + type } else { "" } }}


# Run tests and generate coverage report
[group: "qa"]
coverage:
    poetry run pytest --cov=app --cov-report=term-missing


# Test connectivity to PostgreSQL
[group: "db"]
postgres:
    poetry run python app/common/alchemy.py
alias db-connect := postgres


# A recipe to show the startup message for the dev environment
_dev_message debug='false':
    @echo "Powercord is {{ if debug == "debug" { "running in DEBUG mode" } else { "starting" } }}! Please wait ~1 minute for all services to start.  Use Ctrl+C to exit."


# Run Powercord stack locally.
[group: "dev"]
[parallel]
dev: _dev_message bot api ui


# Run Powercord stack locally in debug mode.
[group: "dev"]
[parallel]
dev-debug: (_dev_message "debug") (bot "debug") (api "debug") (ui "debug")


# Restart only the UI frontend (kills stale process first)
[group: "dev"]
restart-ui debug='false':
    @just _kill_port 5001
    @just ui {{debug}}


# Run Powercord locally(containerized)
[group: "dev"]
run:
    docker compose up --build


# Run Powercord locally(containerized) and reset database volume
[group: "dev"]
run-clean:
    docker compose down -v
    docker compose up --build


# Run verification tests for the new dashboard features
[group: "qa"]
verify-dashboard:
    poetry run pytest tests/unit/test_internal_server.py tests/unit/test_ui_components.py tests/integration/test_admin_routes.py tests/integration/test_public_home.py


# Resets Dashboard Admins (Clears the admin_users table)
[group: "db"]
reset-admins:
    poetry run python app/db/reset_dashboard_admins.py


# Add a dashboard admin. Usage: just add-admin <user_id> [comment]
[group: "db"]
add-admin user_id comment="Added via CLI":
    poetry run python app/db/add_admin.py {{user_id}} --comment "{{comment}}"


# Remove a dashboard admin. Usage: just remove-admin <user_id>
[group: "db"]
remove-admin user_id:
    poetry run python app/db/remove_admin.py {{user_id}}


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


# Add a third-party API key. Usage: just add-api-key <name> [scopes]
[group: "db"]
add-api-key name scopes='["global"]':
    poetry run python app/db/manage_api_keys.py add {{name}} --scopes '{{scopes}}'


# Revoke a third-party API key. Usage: just revoke-api-key <id>
[group: "db"]
revoke-api-key id:
    poetry run python app/db/manage_api_keys.py revoke {{id}}


# List all third-party API keys
[group: "db"]
list-api-keys:
    poetry run python app/db/manage_api_keys.py list



# Import extension justfiles (optional, only loaded when present)
import? 'app/extensions/midi_library/justfile'
import? 'app/extensions/honeypot/justfile'
import? 'app/extensions/example/justfile'
import? 'app/extensions/utilities/justfile'


# Export the database to a file. Usage: just db-export [file]
[group: "db"]
db-export file="powercord-export.sql":
    poetry run python app/db/db_tools.py export "{{file}}"


# Import the database from a file. Usage: just db-import <file>
[group: "db"]
db-import file:
    poetry run python app/db/db_tools.py import "{{file}}"


# =========================================================================
# Deployment
# =========================================================================

gcp_project := `gcloud config get-value project`
gcp_bucket := gcp_project + "-tf-state"

# Run terraform init
[group: "deploy"]
tf-init:
    cd terraform && terraform init -backend-config=bucket={{gcp_bucket}}

# Run terraform plan
[group: "deploy"]
tf-plan:
    cd terraform && terraform plan

# Apply infrastructure changes
[group: "deploy"]
[confirm("Are you sure you want to apply Terraform changes to your infrastructure?")]
tf-apply:
    cd terraform && terraform apply

# Destroy infrastructure
[group: "deploy"]
[confirm("Are you absolutely sure you want to DESTROY all Terraform infrastructure? This process cannot be reversed!")]
tf-destroy:
    cd terraform && terraform destroy

# Build the Powercord Docker image and trigger the CI deployment pipeline
[group: "deploy"]
gcp-build:
    gcloud builds submit --config cloudbuild.yaml .
