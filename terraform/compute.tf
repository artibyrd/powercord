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

      cat << 'EOF' > /etc/systemd/system/backup-sync.service
      [Unit]
      Description=Sync database backups to GCS

      [Service]
      Type=oneshot
      # Run a container to sync the backups to GCS, accessing the same volume as the powercord container
      ExecStart=/usr/bin/docker run --rm --volumes-from=powercord gcr.io/google.com/cloudsdktool/cloud-sdk:slim sh -c "gsutil cp /var/lib/postgresql/data/backups/*.sql gs://powercord-db-backups-${var.project_id}/ || true"
      EOF

      cat << 'EOF' > /etc/systemd/system/backup-sync.timer
      [Unit]
      Description=Run backup sync daily

      [Timer]
      OnCalendar=daily
      Persistent=true

      [Install]
      WantedBy=timers.target
      EOF

      systemctl daemon-reload
      systemctl enable --now backup-sync.timer
    EOT
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [google_project_service.main]
}
