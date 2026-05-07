resource "google_compute_address" "powercord_ip" {
  name   = "powercord-ip"
  region = "us-central1"
}

resource "google_compute_instance" "main" {
  name         = "powercord-instance"
  machine_type = "e2-small"
  zone         = var.zone
  project      = var.project_id
  tags         = ["http-server", "https-server"]

  boot_disk {
    initialize_params {
      image = "cos-cloud/cos-stable"
      size  = 30
    }
  }

  attached_disk {
    source      = google_compute_disk.main.id
    device_name = "powercord-data-disk"
  }


  network_interface {
    network    = "default"
    subnetwork = "default"
    access_config {
      nat_ip = google_compute_address.powercord_ip.address
    }
  }

  service_account {
    email  = google_service_account.compute_sa.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    GCE_ENV_TYPE             = "PROD"
    "google-logging-enabled" = "true"
    gce-container-declaration = yamlencode({
      spec = {
        containers = [
          {
            name  = "powercord"
            image = var.docker_image != "" ? var.docker_image : "us-central1-docker.pkg.dev/${var.project_id}/powercord/powercord-app:latest"
            volumeMounts = [
              {
                name      = "data-disk"
                mountPath = "/var/lib/postgresql/data"
                readOnly  = false
              }
            ]
          }
        ]
        volumes = [
          {
            name = "data-disk"
            gcePersistentDisk = {
              pdName = "powercord-data-disk"
              fsType = "ext4"
            }
          }
        ]
        restartPolicy = "Always"
      }
    })
    startup-script = <<-EOT
      #!/bin/bash
      
      # Auto-resize the persistent data disk if it was expanded
      resize2fs /dev/sdb || true

      cat << 'SERVICEEOF' > /etc/systemd/system/backup-sync.service
      [Unit]
      Description=Sync database backups to GCS

      [Service]
      Type=oneshot
      ExecStart=/bin/bash -c '\
        CONTAINER_ID=$(docker ps --filter "label=io.kubernetes.container.name=powercord" --format "{{.ID}}" | head -1); \
        if [ -z "$CONTAINER_ID" ]; then echo "ERROR: No powercord container found" >&2; exit 1; fi; \
        echo "Syncing backups from container $CONTAINER_ID..."; \
        docker run --rm --volumes-from="$CONTAINER_ID" gcr.io/google.com/cloudsdktool/cloud-sdk:slim \
          sh -c "gsutil cp /var/lib/postgresql/data/backups/*.sql.gz gs://powercord-db-backups-${var.project_id}/" \
        && echo "Backup sync to GCS completed successfully." \
        || { echo "ERROR: Backup sync to GCS failed" >&2; exit 1; }'
      SERVICEEOF

      cat << 'TIMEREOF' > /etc/systemd/system/backup-sync.timer
      [Unit]
      Description=Run backup sync daily

      [Timer]
      OnCalendar=*-*-* 04:00:00
      Persistent=true

      [Install]
      WantedBy=timers.target
      TIMEREOF

      systemctl daemon-reload
      systemctl enable --now backup-sync.timer
    EOT
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [google_project_service.main]
}
