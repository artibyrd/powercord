resource "google_compute_disk" "main" {
  name    = "powercord-data-disk"
  type    = "pd-standard"
  zone    = var.zone
  size    = 10
  project = var.project_id

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.main]
}

resource "google_storage_bucket" "db_backup" {
  name          = "powercord-db-backups-${var.project_id}"
  location      = "US" # Modify as needed
  force_destroy = false
  project       = var.project_id

  lifecycle_rule {
    condition {
      age = 21
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "compute_backup_writer" {
  bucket = google_storage_bucket.db_backup.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.compute_sa.email}"
}
