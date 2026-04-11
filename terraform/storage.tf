resource "google_compute_disk" "data_disk" {
  name    = "powercord-data-disk"
  type    = "pd-standard"
  zone    = var.zone
  size    = 10
  project = var.project_id

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.enabled_apis]
}
