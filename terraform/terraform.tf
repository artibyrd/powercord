terraform {
  required_version = ">= 1.7"

  backend "gcs" {
    # Bucket name will be provided via backend-config during init
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}
