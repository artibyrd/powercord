resource "google_compute_firewall" "allow_http" {
  name    = "allow-http-https"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["http-server", "https-server"]

  depends_on = [google_project_service.main]
}
