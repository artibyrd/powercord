import logging
import os
import subprocess
from pathlib import Path

import google.auth
import requests
from dotenv import dotenv_values, load_dotenv
from google.api_core import exceptions as google_exceptions
from google.cloud import secretmanager

_ENV_LOADED = False


def check_gce_metadata(metadata_key: str) -> str | None:
    """
    Fetches a specific metadata value from the GCE metadata server.
    This is used to determine the execution environment (e.g., PROD, QA).
    Returns None if the server is unavailable (e.g., running locally).
    """
    url = f"http://metadata.google.internal/computeMetadata/v1/instance/attributes/{metadata_key}"
    try:
        response = requests.get(url, headers={"Metadata-Flavor": "Google"}, timeout=2)
        response.raise_for_status()
        return str(response.text)
    except requests.exceptions.RequestException:
        # This is an expected and normal condition when not running on a GCE VM.
        logging.info("GCE Metadata server not available. Assuming non-GCE environment.")
        return None


def _get_project_id() -> str | None:
    """
    Gets the default GCP project ID from the environment.
    It first tries the `google-auth` library, then falls back to the `gcloud` CLI.
    """
    try:
        _, project_id = google.auth.default()
        if project_id:
            return str(project_id)
    except google.auth.exceptions.DefaultCredentialsError:
        pass  # Fall through to the gcloud CLI method.

    # Fallback to gcloud CLI if the library can't find the project ID.
    try:
        project_id = subprocess.check_output(["gcloud", "config", "get-value", "project"]).decode("utf-8").rstrip()
        return str(project_id)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logging.error(
            "Could not determine GCP project ID. Ensure you are logged in (`gcloud auth login`) and have a project set (`gcloud config set project <PROJECT_ID>`)."
        )
        return None


def _get_secret(client: secretmanager.SecretManagerServiceClient, key: str, project_id: str) -> str | None:
    """
    Fetches the latest version of a secret from Google Secret Manager.
    Returns the secret value as a string, or None if not found.
    """
    name = f"projects/{project_id}/secrets/{key}/versions/latest"
    try:
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except google_exceptions.NotFound:
        logging.warning(f"Secret '{key}' not found in project '{project_id}'.")
        return None


def load_env():
    """
    Loads environment variables. In a GCE environment, it loads secrets from
    Google Secret Manager. In a local environment, it loads from a `.env` file.
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        # This function can be called from multiple modules during startup.
        # This check ensures we only load the environment once per process.
        logging.debug("Environment variables already loaded. Skipping.")
        return

    env_type = check_gce_metadata("GCE_ENV_TYPE")

    if not env_type:
        # Local environment: load from .env file.
        logging.info("Non-GCE environment detected. Loading variables from '.env' file.")
        # The project root is two levels up from this file (app/common/gsm_loader.py)
        project_root = Path(__file__).resolve().parents[2]
        dotenv_path = project_root / ".env"
        if dotenv_path.exists():
            load_dotenv(dotenv_path=dotenv_path)
            logging.info(f"Loaded environment variables from {dotenv_path}.")
        else:
            logging.warning(f"Local '.env' file not found at {dotenv_path}. No local environment variables loaded.")
        _ENV_LOADED = True
        return

    # Deployed GCE environment: load from Google Secret Manager.
    logging.info(f"GCE environment '{env_type}' detected. Loading secrets from Google Secret Manager.")
    project_id = _get_project_id()
    if not project_id:
        return

    # The project root is two levels up from this file (app/common/gsm_loader.py)
    project_root = Path(__file__).resolve().parents[2]
    dotenv_path = project_root / ".example.env"
    if not dotenv_path.exists():
        logging.warning(f"Manifest file '.example.env' not found at {dotenv_path}. No secrets will be loaded.")
        return
    dotenvs = dotenv_values(dotenv_path=dotenv_path)
    logging.debug(f"Secrets to load from manifest: {list(dotenvs.keys())}")

    g_client = secretmanager.SecretManagerServiceClient()
    for key in dotenvs.keys():
        secret_value = _get_secret(g_client, key, project_id)
        if secret_value is not None:
            os.environ.setdefault(key, secret_value)
            logging.debug(f"Setting env var '{key}'.")

    _ENV_LOADED = True


if __name__ == "__main__":
    load_env()
