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

### 1.3. Populate Secrets in Secret Manager

Powercord securely loads all environment variables directly from Google Secret Manager at runtime. Our Terraform code is now configured to automatically ingest these values from a `.env.prod` file during the deployment plan.

Before running `tf-apply`, make sure to instantiate your production secrets:

1. Copy the template:
   ```bash
   cp .env.prod.example .env.prod
   ```
2. Open `.env.prod` and carefully fill in your secure strings (ensuring they remain enclosed in quotes). 
3. When you run `just tf-apply`, Terraform will safely extract these values and automatically instantiate `google_secret_manager_secret_version` components in your GCP project without requiring you to run `gcloud secrets versions add` manually!

### 1.4. Deploy Infrastructure via Terraform (Bootstrap)

Terraform will automatically enable APIs, create your Artifact Registry, provision your Service Accounts, and upload your `.env.prod` secrets.

> [!IMPORTANT]
> **Bootstrap Requirement (Do not skip)**: You must execute your inaugural `just tf-apply` locally from your machine!
>
> You cannot initialize the project by immediately running the `just gcp-build` CI pipeline because of a structural paradox: Cloud Build needs an existing Artifact Registry to store your built Docker image, but your Artifact Registry doesn't exist until Terraform creates it! 
> 
> By running `tf-apply` locally first, you securely scaffold all foundational cloud components (including spinning up your Compute VM using a dummy image path). Once the local run succeeds and your Artifact Registry physically exists, the CI pipeline can safely take over subsequent updates.

Run the Just commands to plan and apply the infrastructure:

```bash
just tf-init
just tf-plan
just tf-apply
```

_(Note: You will be prompted to confirm the execution before resources are provisioned)._

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

---

## Part 3: Database Management in Production

The production environment is configured to automatically and securely manage your database backups. Because the production Docker image is built to be lightweight, it does not include development tools like `just` or `poetry`. Instead, database management relies on built-in automated systems and direct container commands.

### Automated Daily Backups
The core Powercord application runs a scheduled background task that automatically creates a full database backup (`.sql` file) every 24 hours.
- **Location:** Backups are stored in the persistent volume mapped to `/var/lib/postgresql/data/backups`.
- **Retention:** The system automatically prunes backups older than 7 days to conserve disk space.
- **Cloud Sync:** The host Google Compute Engine VM runs a daily `systemd` timer (configured via Terraform) that seamlessly syncs these local backups to your `powercord-db-backups-<your-project-id>` Cloud Storage bucket. This ensures your data is safely stored off-instance without coupling the core Python application to GCP-specific logic.

### Restoring a Database
If you need to restore the database from a backup (e.g., migrating from a legacy system or recovering from a failure), follow this standard procedure:

#### 1. Transfer the Data File
Upload your `.sql` dump file from your local machine to the Compute Engine instance:
```bash
gcloud compute scp your_dump_file.sql powercord-instance:~ --zone us-central1-a
```

#### 2. SSH into the Instance and Find the Container
Connect to the virtual machine:
```bash
gcloud compute ssh powercord-instance --zone us-central1-a
```
Find the running Powercord Docker container's ID (or name):
```bash
docker ps
```

#### 3. Copy the File into the Container
Copy the dump file from the VM's home directory directly into the running container's `/app` directory:
```bash
docker cp your_dump_file.sql <CONTAINER_ID>:/app/your_dump_file.sql
```

#### 4. Execute the Restore Command
Run the database import script directly inside the Docker container:
```bash
docker exec -it <CONTAINER_ID> python app/db/db_tools.py import /app/your_dump_file.sql
```

*(Note: Once the process completes, you can safely delete `your_dump_file.sql` from both the container and the VM to free up disk space).*

