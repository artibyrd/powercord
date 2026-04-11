locals {
  services = [
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com"
  ]

  expected_secrets = [
    "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "DB_HOST", "DISCORD_TOKEN",
    "DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "SESSION_KEY", "API_RELOAD_URL",
    "API_RELOAD_KEY", "BOT_RELOAD_URL", "BOT_RELOAD_KEY", "INITIAL_ADMIN_DISCORD_ID",
    "BASE_URL", "EXAMPLE_WEBHOOK_URL", "BUCKET_URL", "GCP_PROJECT", "GOOGLE_APPLICATION_CREDENTIALS"
  ]
}
