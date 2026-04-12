resource "google_secret_manager_secret" "main" {
  for_each  = local.parsed_secrets
  secret_id = each.key
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.main]
}

resource "google_secret_manager_secret_version" "main" {
  for_each    = local.parsed_secrets
  secret      = google_secret_manager_secret.main[each.key].id
  secret_data = each.value
}
