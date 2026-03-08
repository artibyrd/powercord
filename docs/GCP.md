# Google Cloud Platform Deployment Guide

This guide provides all the necessary steps to configure a Google Cloud Platform (GCP) project and deploy the Powercord application using Cloud Build and a Compute Engine (GCE) instance.

The guide is split into two parts:
*   **Part 1: Initial Project and Infrastructure Setup** - These are one-time steps you perform when setting up a new GCP project for this application.
*   **Part 2: Application Deployment and Updates** - These are the steps you will repeat each time you want to deploy a new version of the application.

---

## Part 1: Initial Project and Infrastructure Setup (One-Time Only)

### 1.1. Prerequisites

*   A Google Cloud Platform account with an active billing account.
*   The [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and authenticated on your local machine.

First, log in and initialize the gcloud CLI:

```bash
gcloud auth login
gcloud init
```

Set your project ID for all subsequent commands. Replace `[YOUR_PROJECT_ID]` with your actual GCP project ID.

```bash
gcloud config set project [YOUR_PROJECT_ID]
```

### 1.2. Enable Required APIs

The deployment process requires several GCP services. Enable their APIs with the following command:

```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com
```

### 1.3. Create an Artifact Registry Repository

This repository will store the Docker image of your application.

```bash
gcloud artifacts repositories create powercord \
  --repository-format=docker \
  --location=us-central1 \
  --description="Docker repository for Powercord"
```

### 1.4. Store Secrets in Secret Manager

For security, we'll store sensitive data like database credentials and your Discord bot token in Secret Manager.

**Important:** Replace the placeholder values (`your_..._here`) with your actual secrets.

```bash
# Database User
echo -n "powercord_user" | gcloud secrets create POSTGRES_USER --replication-policy="automatic" --data-file=-

# Database Password (use a strong, unique password)
echo -n "your_strong_password_here" | gcloud secrets create POSTGRES_PASSWORD --replication-policy="automatic" --data-file=-

# Database Name
echo -n "powercord_db" | gcloud secrets create POSTGRES_DB --replication-policy="automatic" --data-file=-

# Discord Bot Token
echo -n "your_discord_bot_token_here" | gcloud secrets create DISCORD_TOKEN --replication-policy="automatic" --data-file=-
```

### 1.5. Create Service Accounts and Grant Permissions

The service accounts for Cloud Build and Compute Engine need specific permissions to perform their tasks.

#### Create a dedicated Service Account for Cloud Build
```bash
gcloud iam service-accounts create cloud-build-packer-sa \
  --display-name "Cloud Build Packer Service Account"
```

#### Grant Permissions to the Cloud Build Service Account
```bash
PROJECT_ID=$(gcloud config get-value project)
SERVICE_ACCOUNT_EMAIL="cloud-build-packer-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Allow the SA to manage GCE instances and images (for Packer)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/compute.instanceAdmin.v1"

# Allow the SA to act as the default GCE service account
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

# Allow the SA to write to Artifact Registry
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/artifactregistry.writer"
```

#### Grant Permissions to the GCE Instance
The running GCE instance needs to access secrets from Secret Manager. Grant this permission to the default Compute Engine service account.
```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
GCE_SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${GCE_SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
```

### 1.6. Create Persistent Disk and Firewall Rule

These resources are created once and persist across all deployments.

1.  **Create a Persistent Disk**: This disk will store your PostgreSQL data.
    ```bash
    gcloud compute disks create powercord-data-disk --size=10GB --zone=us-central1-a
    ```
2.  **Create a Firewall Rule**: This allows HTTP traffic to your instance.
    ```bash
    gcloud compute firewall-rules create allow-http --allow=tcp:80 --target-tags=http-server
    ```

---

## Part 2: Application Deployment and Updates

Follow these steps every time you want to deploy a new version of your application.

### 2.1. Build a New Version

This command runs the Cloud Build pipeline. It builds a new Docker image, pushes it to Artifact Registry, and then uses Packer to create a new, versioned GCE VM image.
```bash
gcloud builds submit --config cloudbuild.yaml .
```

### 2.2. Launch the Instance (First Time Only)

If you are deploying for the very first time, run this command after your first successful build. It creates the instance from your new image and attaches the persistent disk you created earlier.

```bash
gcloud compute instances create powercord-instance \
  --zone=us-central1-a \
  --image-family=powercord-app \
  --machine-type=e2-small \
  --scopes=cloud-platform \
  --tags=http-server \
  --disk=name=powercord-data-disk,auto-delete=no,boot=no
```

### 2.3. Update an Existing Instance (Re-deploy)

For all subsequent deployments, you will update the existing instance by recreating it with the latest VM image. This process preserves your persistent data disk and causes only a few minutes of downtime.

**This is the standard command for re-deploying your application.**

1.  **Delete the current instance**: The `--keep-disks=boot` flag is important. It ensures the boot disk of the old instance is not deleted, which can be useful for rollbacks. Your `powercord-data-disk` is not a boot disk and will be preserved by default.
    ```bash
    gcloud compute instances delete powercord-instance --zone=us-central1-a --keep-disks=boot
    ```
2.  **Re-create the instance**: This command is identical to the one used for the first-time launch. It will automatically pick up the newest image from the `powercord-app` family and re-attach your existing `powercord-data-disk`.
    ```bash
    gcloud compute instances create powercord-instance \
      --zone=us-central1-a \
      --image-family=powercord-app \
      --machine-type=e2-small \
      --scopes=cloud-platform \
      --tags=http-server \
      --disk=name=powercord-data-disk,auto-delete=no,boot=no
    ```

Once these steps are complete, your Powercord application will be running on the GCE instance. You can find its external IP address in the GCP Console under "Compute Engine".  You can use this to map a domain name to the frontend if you like.