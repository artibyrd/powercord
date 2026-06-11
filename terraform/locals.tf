locals {
  services = [
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com"
  ]

  env_prod_content = fileexists("${path.module}/../.env.prod") ? file("${path.module}/../.env.prod") : ""

  raw_secrets = {
    for line in split("\n", local.env_prod_content) :
    trimspace(split("=", line)[0]) => trim(trimspace(join("=", slice(split("=", line), 1, length(split("=", line))))), "\"'")
    if length(trimspace(line)) > 0 && substr(trimspace(line), 0, 1) != "#"
  }

  # Filter out empty values because GCP Secret Manager requires a non-empty payload
  parsed_secrets = {
    for k, v in local.raw_secrets : k => v
    if v != ""
  }

  expected_secrets = keys(local.parsed_secrets)
}
