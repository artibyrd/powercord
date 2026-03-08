#!/bin/bash
set -e
set -x

# --- Configuration ---
CONTAINER_NAME="powercord-app"
# Use the stable symlink for the persistent disk to avoid issues with device name changes (e.g., /dev/sdb, /dev/sdc)
PERSISTENT_DISK_DEVICE="/dev/disk/by-id/google-powercord-data-disk"
MOUNT_POINT="/mnt/disks/data"
POSTGRES_DATA_DIR="${MOUNT_POINT}/postgres"

# --- Get instance metadata ---
DOCKER_IMAGE=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/docker_image" -H "Metadata-Flavor: Google")
PROJECT_ID=$(curl -s "http://metadata.google.internal/computeMetadata/v1/project/project-id" -H "Metadata-Flavor: Google")

# --- Mount persistent disk for database data ---
echo "Mounting persistent disk..."
sudo mkdir -p ${MOUNT_POINT}
if ! sudo mountpoint -q ${MOUNT_POINT}; then
  # Check if the disk is formatted
  if ! sudo blkid -s TYPE -o value ${PERSISTENT_DISK_DEVICE}; then
    echo "Formatting persistent disk..."
    sudo mkfs.ext4 -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard ${PERSISTENT_DISK_DEVICE}
  fi
  sudo mount -o discard,defaults ${PERSISTENT_DISK_DEVICE} ${MOUNT_POINT}
fi
sudo chmod a+w ${MOUNT_POINT}
mkdir -p ${POSTGRES_DATA_DIR}

# --- Fetch secrets from Google Secret Manager ---
echo "Fetching secrets..."
DB_USER=$(gcloud secrets versions access latest --secret="POSTGRES_USER" --project="${PROJECT_ID}")
DB_PASS=$(gcloud secrets versions access latest --secret="POSTGRES_PASSWORD" --project="${PROJECT_ID}")
DB_NAME=$(gcloud secrets versions access latest --secret="POSTGRES_DB" --project="${PROJECT_ID}")
BOT_TOKEN=$(gcloud secrets versions access latest --secret="DISCORD_TOKEN" --project="${PROJECT_ID}")

# --- Run the Docker container ---
echo "Starting Docker container..."

# Stop and remove any existing container
docker stop ${CONTAINER_NAME} || true
docker rm ${CONTAINER_NAME} || true

# Pull the latest image
docker pull "${DOCKER_IMAGE}"

# Run the new container
docker run -d --restart=always \
  --name ${CONTAINER_NAME} \
  -p 80:80 \
  -v "${POSTGRES_DATA_DIR}:/var/lib/postgresql/data" \
  -e POSTGRES_USER="${DB_USER}" \
  -e POSTGRES_PASSWORD="${DB_PASS}" \
  -e POSTGRES_DB="${DB_NAME}" \
  -e DISCORD_TOKEN="${BOT_TOKEN}" \
  -e DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}" \
  "${DOCKER_IMAGE}"

echo "Deployment complete."