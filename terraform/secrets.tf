resource "google_secret_manager_secret" "main" {
  for_each  = toset(local.expected_secrets)
  secret_id = each.key
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.main]
}
