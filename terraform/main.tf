locals {
  services = [
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com"
  ]
}

resource "google_project_service" "enabled_apis" {
  for_each           = toset(local.services)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "powercord" {
  location      = var.region
  repository_id = "powercord"
  description   = "Docker repository for Powercord"
  format        = "DOCKER"
  depends_on    = [google_project_service.enabled_apis]
}
