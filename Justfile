# use with https://just.systems

# ---------------------------------------------------------------------------- #
#                                 SETTINGS                                     #
# ---------------------------------------------------------------------------- #

set shell := ["bash", "-cu"]
set export
set dotenv-load
set unstable  # required for [parallel] (lines 105, 109)
set positional-arguments := true

import 'devkit.just'

export PYTHONIOENCODING := "utf8"


# ---------------------------------------------------------------------------- #
#                                 CONSTANTS                                    #
# ---------------------------------------------------------------------------- #

gcp_project := env("POWERCORD_GCP_PROJECT", "")
gcp_bucket := gcp_project + "-tf-state"
gcp_default_image := "us-central1-docker.pkg.dev/" + gcp_project + "/powercord/powercord-app:latest"
gcp_zone := env("POWERCORD_GCP_ZONE", "us-central1-a")
gcp_instance := env("POWERCORD_GCP_INSTANCE", "powercord-instance")


# ---------------------------------------------------------------------------- #
#                               DEFAULT RECIPE                                 #
# ---------------------------------------------------------------------------- #

# Default: List available just commands
default:
    @just --list --unsorted


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

# Run Powercord locally(containerized)
[group: "dev"]
run: _teardown-dev-db
    docker compose up --build

# Run Powercord locally(containerized) and reset database volume
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


# ---------------------------------------------------------------------------- #
#                                 QA COMMANDS                                  #
# ---------------------------------------------------------------------------- #

# Quality Assurance (uses _timed wrapper). Usage: just qa [--fix]
[group: "qa"]
[arg("fix", long, value="true")]
qa fix="false": install (lint fix) (format fix) check test

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

# Type Checking (Mypy)
[group: "qa"]
typecheck:
    just _run-with-status _check
alias mypy := typecheck
alias tc := typecheck

[private]
_check:
    poetry run mypy .

# Fast hermetic pre-commit QA gate (<3s: lint + format + test-gov, zero DB)
[group: "qa"]
check:
    poetry run ruff check .
    poetry run ruff format --check .
    poetry run pytest tests/governance -q

# Run shift-left governance tests (<3s, zero DB)
[group: "qa"]
test-gov:
    poetry run pytest tests/governance -v

# Prime IDE command permissions in fresh workspaces
[group: "dev"]
bootstrap-approvals:
    @just check
    @just typecheck
    @git status -s

# Single-command onboarding & health check
[group: "dev"]
ignite: install check
    @echo "Powercord environment ignited successfully."

# Inspect git status across all ecosystem repositories
[group: "vcs"]
status-all:
    #!/usr/bin/env bash
    set -euo pipefail
    for r in . ../powercord-client ../powercord-agent ../powercord-extensions/* ../powercord-client-extensions/* ../powercord-downstream-server; do
        if [ -d "$r/.git" ]; then
            echo "=== Git Status: $(basename "$(cd "$r" && pwd)") ==="
            (cd "$r" && git status -s)
        fi
    done

# Create or switch to a feature branch (never work directly on main)
[group: "vcs"]
branch name:
    git checkout -b {{name}} 2>/dev/null || git checkout {{name}}

# Incremental commit on feature branch gated by pre-commit check
[group: "vcs"]
commit msg: check
    #!/usr/bin/env bash
    current=$(git symbolic-ref --short HEAD 2>/dev/null)
    if [ "$current" = "main" ]; then
        echo "ERROR: Direct commits to main prohibited by inv-branch-pr-review-gate. Use: just branch feat/<name>"
        exit 1
    fi
    git add -A
    git commit -m "{{msg}}"

# Push feature branch and open a GitHub pull request
[group: "vcs"]
pr-create title="":
    #!/usr/bin/env bash
    current=$(git symbolic-ref --short HEAD 2>/dev/null)
    if [ "$current" = "main" ]; then
        echo "ERROR: Cannot open PR from main branch."
        exit 1
    fi
    git push -u origin "$current"
    if [ -n "{{title}}" ]; then
        gh pr create --title "{{title}}" --fill
    else
        gh pr create --fill
    fi

# Check pull request status for the current branch
[group: "vcs"]
pr-status:
    gh pr status

# Release tag sequence (run on main after PR merge)
[group: "vcs"]
release version message: check
    #!/usr/bin/env bash
    current=$(git symbolic-ref --short HEAD 2>/dev/null)
    if [ "$current" != "main" ]; then
        echo "ERROR: Releases must be tagged on the main branch after PR merge."
        exit 1
    fi
    poetry version {{version}}
    git add Justfile pyproject.toml tests/governance/test_version_and_manifest_parity.py
    git commit --allow-empty -m "chore(release): bump version to {{version}}"
    git tag -a "v{{version}}" -m "{{message}}"
    git push origin main "v{{version}}"
    echo "Release v{{version}} tagged and pushed successfully."

# Run tests. Usage: just test [--type unit|integration|all]
[group: "qa"]
[arg("type", long)]
test type="": _ensure-db lint
    just _run-with-status _test {{ if type != "" { "--type " + type } else { "" } }}
alias t := test

[private]
[arg("type", long)]
_test type="":
    #!/usr/bin/env bash
    if [ "{{type}}" = "all" ]; then
      poetry run pytest tests
    elif [ "{{type}}" != "" ]; then
      poetry run pytest tests -m "{{type}}"
    else
      poetry run pytest tests -m "not integration"
    fi

# Run tests and generate coverage report
[group: "qa"]
coverage: _ensure-db lint
    poetry run pytest --cov=app --cov-report=term-missing

# Run verification tests for the new dashboard features
[group: "qa"]
verify-dashboard: _ensure-db lint
    poetry run pytest tests/unit/test_internal_server.py tests/unit/test_ui_components.py tests/integration/test_admin_routes.py tests/integration/test_public_home.py


# ---------------------------------------------------------------------------- #
#                                 DB COMMANDS                                  #
# ---------------------------------------------------------------------------- #

# Upgrade the database to the latest version (see also: _wait-for-compose-db)
[group: "db"]
db-upgrade: _ensure-db
    poetry run python -c "from app.common.extension_manager import _update_alembic_ini; _update_alembic_ini()"
    poetry run alembic upgrade heads

# Create a new migration revision
[group: "db"]
db-revision message: _ensure-db
    poetry run python -c "from app.common.extension_manager import _update_alembic_ini; _update_alembic_ini()"
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

# Add a third-party API key. Usage: just add-api-key <name> [--scopes '["global"]'] [--key <legacy_key>]
[group: "db"]
[arg("scopes", long)]
[arg("key", long)]
add-api-key name scopes='["global"]' key="": _ensure-db
    #!/usr/bin/env bash
    if [ -n "{{key}}" ]; then
      poetry run python app/db/manage_api_keys.py add "{{name}}" --scopes '{{scopes}}' --key "{{key}}"
    else
      poetry run python app/db/manage_api_keys.py add "{{name}}" --scopes '{{scopes}}'
    fi

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
[arg("migration", long, value="true")]  # BEGIN LEGACY: v2 data migration flag — see docs/LEGACY_V2_MIGRATION.md
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

# Import internal extension justfiles (optional, only loaded when present)
import? 'app/extensions/example/extension.just'
import? 'app/extensions/utilities/extension.just'

# Install an extension from a local directory or Git repository
[group: "extensions"]
ext-install source_path:
    poetry run python -m app.common.extension_manager install {{source_path}}

# Uninstall an extension by name
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
tf-init: _require-gcp
    just _run-with-status _tf-init

[private]
_tf-init:
    cd terraform && terraform init -backend-config=bucket={{gcp_bucket}}

# Run terraform plan locally
[group: "deploy"]
[arg("docker_image", long)]
tf-plan docker_image=gcp_default_image: _require-gcp
    just _run-with-status _tf-plan {{docker_image}}

[private]
_tf-plan docker_image:
    cd terraform && terraform plan -var=project_id={{gcp_project}} -var=docker_image={{docker_image}}

# Apply infrastructure changes locally
[group: "deploy"]
[confirm("Are you sure you want to manually apply Terraform changes locally?")]
[arg("docker_image", long)]
tf-apply docker_image=gcp_default_image: _require-gcp
    cd terraform && terraform apply -var=project_id={{gcp_project}} -var=docker_image={{docker_image}}

# Destroy infrastructure
[group: "deploy"]
[confirm("Are you absolutely sure you want to DESTROY all Terraform infrastructure? This process cannot be reversed!")]
[arg("docker_image", long)]
tf-destroy docker_image=gcp_default_image: _require-gcp
    cd terraform && terraform destroy -var=project_id={{gcp_project}} -var=docker_image={{docker_image}}

# Build the Powercord Docker image and trigger the CI deployment pipeline
[group: "deploy"]
gcp-build: _require-gcp
    gcloud builds submit --config cloudbuild.yaml . --project={{gcp_project}}
    @echo "Resetting the VM instance to pull the new image..."
    gcloud compute instances reset {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}}

# Inspect live production VM, container, current image, and backup availability
[group: "prod"]
prod-status: _require-gcp
    #!/usr/bin/env bash
    set -euo pipefail
    echo "================================================================================"
    echo "                     POWERCORD PRODUCTION STATUS ({{gcp_project}})"
    echo "================================================================================"
    echo "→ Checking Compute Engine VM ({{gcp_instance}} in {{gcp_zone}})..."
    vm_status=$(gcloud compute instances describe {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}} --format="value(status)" 2>/dev/null || echo "UNKNOWN")
    vm_ip=$(gcloud compute instances describe {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}} --format="value(networkInterfaces[0].accessConfigs[0].natIP)" 2>/dev/null || echo "UNKNOWN")
    echo "  VM Status : ${vm_status}"
    echo "  Public IP : ${vm_ip}"

    echo ""
    echo "→ Checking Container Declaration Metadata..."
    current_image=$(gcloud compute instances describe {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}} --format="value(metadata[gce-container-declaration])" 2>/dev/null | sed -n 's/.*"image": "\([^"]*\)".*/\1/p' | head -1)
    if [ -z "${current_image}" ]; then current_image="UNKNOWN"; fi
    echo "  Declared Image : ${current_image}"

    if [ -f "backups/last_known_good.json" ]; then
        echo ""
        echo "→ Last Known Good Record (backups/last_known_good.json):"
        cat backups/last_known_good.json
    fi

    echo ""
    echo "→ Checking Recent Backups in GCS (gs://powercord-db-backups-{{gcp_project}}/)..."
    gcloud storage ls --project={{gcp_project}} "gs://powercord-db-backups-{{gcp_project}}/" 2>/dev/null | tail -n 5 || echo "  (Could not list backups or bucket empty)"

    if [ "${vm_status}" = "RUNNING" ] && [ "${vm_ip}" != "UNKNOWN" ]; then
        echo ""
        echo "→ Pinging Live Endpoints on http://${vm_ip}..."
        curl -s -o /dev/null -w "  / (Web UI)  : HTTP %{http_code}\n" --connect-timeout 5 "http://${vm_ip}/" || echo "  / (Web UI)  : TIMEOUT/FAILED"
    fi
    echo "================================================================================"

# Stream live logs from the production container
[group: "prod"]
prod-logs tail="50": _require-gcp
    gcloud compute ssh {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}} --command="docker logs --tail {{tail}} -f \$(docker ps -q | head -1)"

# Open an interactive SSH session to the production VM
[group: "prod"]
prod-ssh: _require-gcp
    gcloud compute ssh {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}}

# Trigger an immediate database backup on the production container and sync to GCS & local
[group: "prod"]
prod-backup tag="pre-deploy": _require-gcp
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p backups
    timestamp=$(date -u +%Y%m%d_%H%M%SZ)
    backup_name="powercord_db_backup_{{tag}}_${timestamp}.sql.gz"
    echo "=== Triggering Live Production Database Backup ==="
    echo "  Target: ${backup_name}"

    # 1. Trigger backup creation inside running container
    gcloud compute ssh {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}} --command="
      CONTAINER_ID=\$(docker ps -q | head -1)
      if [ -z \"\$CONTAINER_ID\" ]; then echo 'ERROR: No running container found' >&2; exit 1; fi
      echo 'Creating database dump inside container '\$CONTAINER_ID'...'
      docker exec \"\$CONTAINER_ID\" /app/.venv/bin/python -c \"from app.db.db_tools import BackupService; BackupService.create_daily_backup()\"
    "

    # 2. Stream latest container backup directly over SSH into local backups/
    echo "→ Streaming latest container backup to backups/${backup_name}..."
    gcloud compute ssh {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}} --command="
      CONTAINER_ID=\$(docker ps -q | head -1)
      LATEST=\$(docker exec \"\$CONTAINER_ID\" ls -t /var/lib/postgresql/data/backups/ | head -1)
      docker exec \"\$CONTAINER_ID\" cat /var/lib/postgresql/data/backups/\$LATEST
    " > "backups/${backup_name}"

    # Verify gzip integrity of the local download
    gzip -t "backups/${backup_name}"
    echo "  ✓ Local backup integrity verified."

    # 3. Upload verified backup to GCS
    echo "→ Uploading backups/${backup_name} to GCS..."
    gcloud storage cp --project={{gcp_project}} "backups/${backup_name}" "gs://powercord-db-backups-{{gcp_project}}/${backup_name}"

    # 4. Capture currently running image tag and write manifest
    current_image=$(gcloud compute instances describe {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}} --format="value(metadata[gce-container-declaration])" 2>/dev/null | sed -n 's/.*"image": "\([^"]*\)".*/\1/p' | head -1)
    echo "→ Updating backups/last_known_good.json..."
    printf '{\n  "timestamp": "%s",\n  "tag": "%s",\n  "deployed_image": "%s",\n  "gcs_backup": "%s",\n  "local_backup": "%s"\n}\n' \
        "${timestamp}" "{{tag}}" "${current_image}" "gs://powercord-db-backups-{{gcp_project}}/${backup_name}" "backups/${backup_name}" > backups/last_known_good.json
    echo "✅ Backup completed successfully. Manifest recorded in backups/last_known_good.json"

# Safe production deployment: checks gates, creates mandatory backup, builds, and verifies
[group: "prod"]
prod-deploy: _require-gcp
    #!/usr/bin/env bash
    set -euo pipefail
    echo "================================================================================"
    echo "                     POWERCORD SAFE PRODUCTION DEPLOYMENT"
    echo "================================================================================"

    # Gate 1: Check working trees
    echo "→ Gate 1: Verifying working tree cleanliness..."
    dirty=0
    for r in . ../powercord-extensions/*; do
        if [ -d "$r/.git" ]; then
            status="$(git -C "$r" status --porcelain)"
            if [ "$r" = "." ]; then
                status="$(echo "$status" | grep -v -E "^\s*M\s+(poetry\.lock|pyproject\.toml)$" || true)"
            fi
            if [ -n "$status" ]; then
                echo "  ⚠️ Uncommitted changes in $r"
                dirty=1
            fi
        fi
    done
    if [ "$dirty" -ne 0 ]; then
        echo "ERROR: Working tree is dirty. Commit or stash changes before deploying." >&2
        exit 1
    fi
    echo "  ✓ Working trees clean."

    # Gate 2: Local Pre-Commit QA Gate
    echo ""
    echo "→ Gate 2: Running hermetic QA gates (just check)..."
    just check
    echo "  ✓ Governance checks passed."

    # Gate 3: Mandatory Pre-Deploy Backup
    echo ""
    echo "→ Gate 3: Executing mandatory pre-deploy production backup..."
    just prod-backup pre-deploy
    echo "  ✓ Backup verified."

    # Gate 4: Cloud Build & VM Reset
    echo ""
    echo "→ Gate 4: Submitting Cloud Build to {{gcp_project}}..."
    gcloud builds submit --config cloudbuild.yaml . --project={{gcp_project}}

    echo "→ Resetting VM {{gcp_instance}} to pull new image..."
    gcloud compute instances reset {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}}

    # Gate 5: Post-Deploy Health Check Polling
    echo ""
    echo "→ Gate 5: Polling health endpoints (waiting up to 90s for container startup)..."
    vm_ip=$(gcloud compute instances describe {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}} --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

    success=0
    for i in {1..30}; do
        if curl -s -f -m 3 "http://${vm_ip}/" >/dev/null 2>&1; then
            echo "  ✓ Endpoint http://${vm_ip}/ responded OK (attempt $i/30)"
            success=1
            break
        fi
        echo "  Waiting for container startup... ($i/30)"
        sleep 3
    done

    if [ "$success" -eq 1 ]; then
        echo ""
        echo "================================================================================"
        echo "✅ DEPLOYMENT SUCCESSFUL! Powercord is running live at http://${vm_ip}/"
        echo "================================================================================"
    else
        echo ""
        echo "================================================================================"
        echo "⚠️ WARNING: Health check timed out after 90s."
        echo "Inspect logs: just prod-logs"
        echo "Rollback:     just prod-rollback"
        echo "================================================================================"
        exit 1
    fi

# Roll back production container to previous known-good image
[group: "prod"]
[confirm("Are you sure you want to ROLL BACK the production container to the previous version?")]
prod-rollback image="": _require-gcp
    #!/usr/bin/env bash
    set -euo pipefail
    target_image="{{image}}"
    if [ -z "${target_image}" ]; then
        if [ -f "backups/last_known_good.json" ]; then
            target_image=$(python3 -c "import json; print(json.load(open('backups/last_known_good.json')).get('deployed_image', ''))")
        fi
    fi

    if [ -z "${target_image}" ]; then
        echo "ERROR: No target image specified and backups/last_known_good.json not found." >&2
        echo "Usage: just prod-rollback image=<IMAGE_URI>" >&2
        exit 1
    fi

    echo "=== Initiating Production Rollback ==="
    echo "  Rolling back to image: ${target_image}"

    # Apply Terraform with the rollback image
    cd terraform && terraform apply -auto-approve -var=project_id={{gcp_project}} -var=docker_image="${target_image}"
    cd ..

    echo "Resetting VM {{gcp_instance}} to pull rollback image..."
    gcloud compute instances reset {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}}

    echo "Rollback applied. Check status with: just prod-status"
    echo "If database schema changes also need restoration, use: just prod-db-restore <backup_file>"

# Restore a database backup into the running production container
[group: "prod"]
[confirm("Are you sure you want to RESTORE the database? Current production tables will be overwritten!")]
prod-db-restore backup_file: _require-gcp
    #!/usr/bin/env bash
    set -euo pipefail
    file="{{backup_file}}"
    if [ ! -f "${file}" ]; then
        echo "ERROR: Backup file ${file} not found locally." >&2
        exit 1
    fi

    echo "=== Restoring Database to Production Container ==="
    echo "  Source file: ${file}"

    if [[ "${file}" == *.gz ]]; then
        zcat "${file}" | gcloud compute ssh {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}} --command="
          CONTAINER_ID=\$(docker ps -q | head -1)
          if [ -z \"\$CONTAINER_ID\" ]; then echo 'ERROR: No running container found' >&2; exit 1; fi
          docker exec -i \"\$CONTAINER_ID\" psql -U powercord -d powercord
        "
    else
        cat "${file}" | gcloud compute ssh {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}} --command="
          CONTAINER_ID=\$(docker ps -q | head -1)
          if [ -z \"\$CONTAINER_ID\" ]; then echo 'ERROR: No running container found' >&2; exit 1; fi
          docker exec -i \"\$CONTAINER_ID\" psql -U powercord -d powercord
        "
    fi
    echo "✅ Database restore completed successfully."



# ---------------------------------------------------------------------------- #
#                                 HELPERS                                      #
# ---------------------------------------------------------------------------- #

# A recipe to show the startup message for the dev environment
[private]
_dev_message debug='false':
    @echo "Powercord is {{ if debug == "true" { "running in DEBUG mode" } else { "starting" } }}! Please wait ~1 minute for all services to start.  Use Ctrl+C to exit."

# Guard: abort with a clear error if GCP project is not configured
[private]
_require-gcp:
    #!/usr/bin/env bash
    if [ -z "$POWERCORD_GCP_PROJECT" ]; then
      echo "Error: POWERCORD_GCP_PROJECT is not set. Set it in .env or export it." >&2
      exit 1
    fi

# Status reporter for nested jobs.
[private]
_run-with-status recipe *args:
    @echo ""
    @echo '{{ CYAN }}→ Running {{ recipe }}...{{ NORMAL }}'
    @just {{ recipe }} {{ args }}
    @echo '{{ GREEN }}✓ {{ recipe }} completed{{ NORMAL }}'
alias rws := _run-with-status

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

# Wrap a recipe execution to print its elapsed time
[private]
_timed recipe *args:
    #!/usr/bin/env bash
    start_time=$(date +%s)
    shift
    just "{{recipe}}" "$@"
    exit_code=$?
    end_time=$(date +%s)
    elapsed=$((end_time - start_time))
    echo "Recipe '{{recipe}}' completed in ${elapsed}s with exit code ${exit_code}."
    exit ${exit_code}
