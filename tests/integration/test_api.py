import pytest
from fastapi.testclient import TestClient

from app.main_api import app

# All tests in this module are integration tests.
pytestmark = pytest.mark.integration

client = TestClient(app)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Hello": "World"}
