import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_api_user
from app.main_api import app


def override_get_current_api_user():
    return {"identity": "system_internal", "scopes": ["default", "global"]}


app.dependency_overrides[get_current_api_user] = override_get_current_api_user

# All tests in this module are integration tests.
pytestmark = pytest.mark.integration

client = TestClient(app)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Hello": "World"}
