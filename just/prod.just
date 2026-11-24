# ---------------------------------------------------------------------------- #
#                           GCP & PRODUCTION COMMANDS                          #
# ---------------------------------------------------------------------------- #

gcp_project := env("POWERCORD_GCP_PROJECT", "")
gcp_bucket := gcp_project + "-tf-state"
gcp_default_image := "us-central1-docker.pkg.dev/" + gcp_project + "/powercord/powercord-app:latest"
gcp_zone := env("POWERCORD_GCP_ZONE", "us-central1-a")
gcp_instance := env("POWERCORD_GCP_INSTANCE", "powercord-instance")

# Guard: abort with a clear error if GCP project is not configured
[private]
_require-gcp:
    #!/usr/bin/env bash
    if [ -z "$POWERCORD_GCP_PROJECT" ]; then
      echo "Error: POWERCORD_GCP_PROJECT is not set. Set it in .env or export it." >&2
      exit 1
    fi

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
    echo "→ Gate 5: Polling health endpoints (waiting up to 180s for container startup)..."
    vm_ip=$(gcloud compute instances describe {{gcp_instance}} --zone={{gcp_zone}} --project={{gcp_project}} --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

    success=0
    for i in {1..60}; do
        if curl -s -f -m 3 "http://${vm_ip}/" >/dev/null 2>&1; then
            echo "  ✓ Endpoint http://${vm_ip}/ responded OK (attempt $i/60, $((i * 3))s elapsed)"
            success=1
            break
        fi
        echo "  Waiting for container startup... ($i/60, $((i * 3))s elapsed)"
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
        echo "⚠️ WARNING: Health check timed out after 180s."
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
