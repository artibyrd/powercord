# Google Cloud Platform Deployment Guide (Terraform)

This guide provides all the necessary steps to configure a Google Cloud Platform (GCP) project and deploy the Powercord application using HashiCorp Terraform and Cloud Build.

We utilize Google Container-Optimized OS (COS) to directly run the Powercord Docker container on a Compute Engine instance, abstracting away the OS configuration.

---

## Part 1: Initial Setup (One-Time)

### 1.1. Prerequisites

*   A Google Cloud Platform account with an active billing account.
*   The [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and authenticated on your local machine.
*   [Terraform](https://developer.hashicorp.com/terraform/downloads) (> 1.7) installed locally.

Authenticate the gcloud CLI and set your project:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project [YOUR_PROJECT_ID]
```

### 1.2. Create Terraform State Bucket

We store Terraform state remotely in a Google Cloud Storage bucket. Create the bucket before running Terraform (replace `[YOUR_PROJECT_ID]`):

```bash
gcloud storage buckets create gs://[YOUR_PROJECT_ID]-tf-state --location=us-central1
```

### 1.3. Deploy Infrastructure via Terraform

Terraform will automatically enable APIs, create your Artifact Registry, provision your Service Accounts, and set up Google Secret Manager for you.

Run the Just commands to plan and apply the infrastructure:

```bash
just tf-init
just tf-plan
just tf-apply
```

_(Note: You will be prompted to confirm the execution before resources are provisioned)._

### 1.4. Populate Secrets in Secret Manager

Powercord securely loads all environment variables directly from Google Secret Manager at runtime. Our Terraform code is now configured to automatically ingest these values from a `.env.prod` file during the deployment plan.

Before running `just tf-apply`, make sure to instantiate your production secrets:

1. Copy the template:
   ```bash
   cp .env.prod.example .env.prod
   ```
2. Open `.env.prod` and carefully fill in your secure strings (ensuring they remain enclosed in quotes). 
3. When you run `just tf-apply`, Terraform will safely extract these values and automatically instantiate `google_secret_manager_secret_version` components in your GCP project without requiring you to run `gcloud secrets versions add` manually!
---

## Part 2: Application Updates (CI/CD)

Whenever you want to deploy a new version of your application, you simply push to the Cloud Build CI pipeline.

```bash
just gcp-build
```

**How it works:**
1. Cloud Build runs the internal QA checks (formatting, tests).
2. It builds the Docker image and pushes it to your Artifact Registry.
3. It natively executes `terraform apply -auto-approve`, identifying the newly built image hash, and rolling the Compute Engine instance automatically!

Downtime is kept to a minimum as the new Instance uses `create_before_destroy` lifecycle rules.
