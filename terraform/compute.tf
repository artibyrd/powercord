resource "google_compute_instance" "main" {
  name         = "powercord-instance"
  machine_type = "e2-small"
  zone         = var.zone
  project      = var.project_id
  tags         = ["http-server"]

  boot_disk {
    initialize_params {
      image = "cos-cloud/cos-stable"
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
      // Ephemeral public IP
    }
  }

  service_account {
    email  = google_service_account.compute_sa.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    GCE_ENV_TYPE              = "PROD"
    gce-container-declaration = yamlencode({
      spec = {
        containers = [
          {
            name  = "powercord"
            image = var.docker_image
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
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [google_project_service.main]
}
