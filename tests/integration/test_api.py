import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_api_user
from app.main_api import app

# All tests in this module are integration tests.
pytestmark = pytest.mark.integration

client = TestClient(app)


def test_read_root():
    def override_get_current_api_user():
        return {"identity": "system_internal", "scopes": ["default", "global"]}

    app.dependency_overrides[get_current_api_user] = override_get_current_api_user

    response = client.get("/")
    print("STATUS", response.status_code)
    print("JSON", response.json())
    assert response.status_code == 200
    assert response.json() == {"Hello": "World"}

    app.dependency_overrides.clear()
