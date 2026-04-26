---
disable-model-invocation: false
name: powercord-gcp-operations
user-invocable: true
description: Use this skill when the user wants to interact with the deployed Powercord production server on GCP, including tasks like database maintenance, rescoring MIDI files, managing API keys, or running any internal python modules in the running Docker container.
---

# Powercord GCP Operations

## Overview

Expert guidance for interacting with the production Powercord server deployed on Google Cloud Platform (GCP). The production environment runs in a containerized environment (Container-Optimized OS) where standard development tools (`just`, `poetry`) are omitted for security and performance. 

This skill explains how to run operations directly against the deployed container using its isolated virtual environment.

## Quick Reference

### 1. SSH into the Production Instance
To access the host virtual machine:
```bash
gcloud compute ssh powercord-instance --zone us-central1-a
```

### 2. Identify the Container
Once inside the VM, find the running Powercord container ID:
```bash
docker ps
```

### 3. The Golden Rule of Execution
Because the production container lacks `just` and `poetry`, **all Python scripts and modules must be executed using the absolute path to the virtual environment's Python binary**:
`/app/.venv/bin/python`

## Common Operations

### Adding or Managing API Keys
Use the `manage_api_keys.py` script. Note that quotes might be necessary for the arguments.

```bash
# Add a new legacy key
docker exec <CONTAINER_ID> /app/.venv/bin/python app/db/manage_api_keys.py add "LuteBot Legacy Key" --scopes '["midi_library"]' --key "your-hardcoded-key"
```

### Running Background Tasks / Modules
When running modules (e.g., MIDI rescoring), remember that you might need to supply required environment variables if the script expects local port connections rather than Docker networking.

```bash
# Rescore MIDI Library
docker exec -e POWERCORD_DB_HOST=localhost:5432 <CONTAINER_ID> /app/.venv/bin/python -m app.extensions.midi_library.rescore
```

*(Note: `POWERCORD_DB_HOST=localhost:5432` is used because inside the container, the app might connect to the sidecar database container via a different host, or if running directly inside the container without compose networking, the variable override guarantees the correct connection.)*

### Database Backup & Restore

#### Manual Restore Process
1. Upload the dump to the VM:
```bash
gcloud compute scp your_dump_file.sql powercord-instance:~ --zone us-central1-a
```
2. Copy the file from the VM into the container:
```bash
docker cp your_dump_file.sql <CONTAINER_ID>:/app/your_dump_file.sql
```
3. Run the import script using the virtual environment python:
```bash
docker exec -it <CONTAINER_ID> /app/.venv/bin/python app/db/db_tools.py import /app/your_dump_file.sql
```
4. Clean up the dump files when complete.

## Troubleshooting

- **Module Not Found Errors**: If you encounter `ModuleNotFoundError`, double-check that you are using `/app/.venv/bin/python` and not the system `python` or `python3` command.
- **Database Connection Errors**: If a script fails to connect to the database, verify that you have provided the necessary environment overrides (e.g., `-e POWERCORD_DB_HOST=localhost:5432`).
- **GCS Permission Errors**: Ensure the Compute Engine service account (`powercord-compute-sa`) has the required IAM roles (e.g., Storage Object Viewer or `storage.buckets.get` permission) to interact with Google Cloud Storage.
