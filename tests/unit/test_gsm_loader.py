from unittest.mock import MagicMock, patch

import pytest
import requests

from app.common.gsm_loader import _get_project_id, _get_secret, check_gce_metadata, load_env

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


def test_check_gce_metadata_success():
    """Verifies that GCE metadata returns successfully when HTTP request gets a proper response."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = "PROD"
        mock_get.return_value = mock_response
        assert check_gce_metadata("GCE_ENV_TYPE") == "PROD"


def test_check_gce_metadata_failure():
    """Verifies that checking GCE metadata fails gracefully and returns None on timeout/error."""
    with patch("requests.get", side_effect=requests.exceptions.RequestException):
        assert check_gce_metadata("GCE_ENV_TYPE") is None


def test_get_project_id_auth_success():
    """Tests successful retrieval of project ID using google.auth."""
    with patch("google.auth.default", return_value=(None, "my-project")):
        assert _get_project_id() == "my-project"


def test_get_project_id_cli_success():
    """Tests obtaining project ID via gcloud CLI fallback when google.auth throws an exception."""
    import google.auth.exceptions

    with patch("google.auth.default", side_effect=google.auth.exceptions.DefaultCredentialsError):
        with patch("subprocess.check_output", return_value=b"my-cli-project\n"):
            assert _get_project_id() == "my-cli-project"


def test_get_project_id_cli_failure():
    """Ensures a None return value if both google.auth and gcloud CLI fallback fail."""
    import subprocess

    import google.auth.exceptions

    with patch("google.auth.default", side_effect=google.auth.exceptions.DefaultCredentialsError):
        with patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "cmd")):
            assert _get_project_id() is None


def test_get_secret_success():
    """Tests successful retrieval and decoding of a secret from SecretManagerServiceClient."""
    client = MagicMock()
    response = MagicMock()
    response.payload.data.decode.return_value = "my-secret-val"
    client.access_secret_version.return_value = response

    assert _get_secret(client, "my-key", "my-project") == "my-secret-val"
    client.access_secret_version.assert_called_once()  # Ensure the Google Cloud SDK backend was invoked


def test_get_secret_not_found():
    """Tests handling of NotFound exceptions when a secret doesn't exist."""
    from google.api_core import exceptions as google_exceptions

    client = MagicMock()
    client.access_secret_version.side_effect = google_exceptions.NotFound("not found")
    assert _get_secret(client, "my-key", "my-project") is None


def test_load_env_already_loaded():
    """Verifies that load_env exits early if environment variables were already loaded."""
    with patch("app.common.gsm_loader._ENV_LOADED", True):
        with patch("app.common.gsm_loader.check_gce_metadata") as mock_check:
            load_env()
            mock_check.assert_not_called()  # We shouldn't even check GCE if loaded = True


@patch("app.common.gsm_loader.check_gce_metadata", return_value=None)
@patch("app.common.gsm_loader.Path")
@patch("app.common.gsm_loader.load_dotenv")
def test_load_env_local(mock_load_dotenv, mock_path, mock_check):
    """Verifies correct local behavior of loading from standard .env file."""
    import app.common.gsm_loader

    app.common.gsm_loader._ENV_LOADED = False

    # Mocking filesystem logic for identifying the .env file path
    mock_env_file = MagicMock()
    mock_env_file.exists.return_value = True

    mock_path.return_value.resolve.return_value.parents = [MagicMock(), MagicMock(), MagicMock()]
    mock_path.return_value.resolve.return_value.parents[2].__truediv__.return_value = mock_env_file

    load_env()

    mock_load_dotenv.assert_called_once_with(dotenv_path=mock_env_file)
    assert app.common.gsm_loader._ENV_LOADED is True
    app.common.gsm_loader._ENV_LOADED = False  # Reset state


@patch("app.common.gsm_loader.check_gce_metadata", return_value="PROD")
@patch("app.common.gsm_loader._get_project_id", return_value="my-project")
@patch("app.common.gsm_loader.Path")
@patch("app.common.gsm_loader.dotenv_values", return_value={"TEST_KEY": "val"})
@patch("app.common.gsm_loader.secretmanager.SecretManagerServiceClient")
@patch("app.common.gsm_loader._get_secret", return_value="secret-val")
@patch("app.common.gsm_loader.os.environ.setdefault")
def test_load_env_gce(
    mock_setdefault, mock_get_secret, mock_client, mock_dotenv_values, mock_path, mock_project, mock_check
):
    """Verifies cloud behavior on GCE: pulling required keys from manifest and resolving values from GSM."""
    import app.common.gsm_loader

    app.common.gsm_loader._ENV_LOADED = False

    # Mocking filesystem logic for interpreting the .example.env manifest
    mock_env_example = MagicMock()
    mock_env_example.exists.return_value = True
    mock_path.return_value.resolve.return_value.parents = [MagicMock(), MagicMock(), MagicMock()]
    mock_path.return_value.resolve.return_value.parents[2].__truediv__.return_value = mock_env_example

    load_env()

    # GSM should load key 'TEST_KEY' based on the manifest definitions and override default environ
    mock_setdefault.assert_called_once_with("TEST_KEY", "secret-val")
    assert app.common.gsm_loader._ENV_LOADED is True
    app.common.gsm_loader._ENV_LOADED = False  # Reset state
