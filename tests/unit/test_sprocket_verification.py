import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.common.alchemy import get_session
from app.db.models import DiscordAuditorConfig
from app.extensions.utilities.sprocket import router

pytestmark = pytest.mark.unit

app = FastAPI()
app.include_router(router)


@pytest.fixture
def client(session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_sprocket_verification_workflow(client, session):
    """
    Verification test case for:
    - Sprocket GET /api/guild/{guild_id}/audit/score
    - Sprocket GET /api/guild/{guild_id}/audit/alerts
    - Sprocket GET /api/guild/{guild_id}/audit/config
    - Sprocket POST /api/guild/{guild_id}/audit/config (full and partial updates)
    """
    guild_id = 999901

    # 1. Verify GET config on an empty/new guild returns default null/empty config
    response = client.get(f"/api/guild/{guild_id}/audit/config")
    assert response.status_code == 200
    data = response.json()
    assert data["staff_separator_role_id"] is None
    assert data["staff_channel_ids"] == []
    assert data["announcement_channel_ids"] == []

    # 2. Verify POST config with a FULL payload
    full_payload = {
        "staff_separator_role_id": 1234567890,
        "staff_channel_ids": [111, 222],
        "announcement_channel_ids": [333, 444],
    }
    response = client.post(f"/api/guild/{guild_id}/audit/config", json=full_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["staff_separator_role_id"] == 1234567890
    assert data["staff_channel_ids"] == [111, 222]
    assert data["announcement_channel_ids"] == [333, 444]

    # Verify database values for full payload
    session.expire_all()
    db_config = session.get(DiscordAuditorConfig, guild_id)
    assert db_config is not None
    assert db_config.staff_separator_role_id == 1234567890
    assert json.loads(db_config.staff_channel_ids) == [111, 222]
    assert json.loads(db_config.announcement_channel_ids) == [333, 444]

    # 3. Verify POST config with a PARTIAL payload (omitting staff_separator_role_id)
    partial_payload = {"staff_channel_ids": [555, 666], "announcement_channel_ids": [777, 888]}
    response = client.post(f"/api/guild/{guild_id}/audit/config", json=partial_payload)
    assert response.status_code == 200
    data = response.json()
    # staff_separator_role_id should remain preserved
    assert data["staff_separator_role_id"] == 1234567890
    assert data["staff_channel_ids"] == [555, 666]
    assert data["announcement_channel_ids"] == [777, 888]

    # Verify database values for partial payload
    session.expire_all()
    db_config = session.get(DiscordAuditorConfig, guild_id)
    assert db_config.staff_separator_role_id == 1234567890  # Preserved!
    assert json.loads(db_config.staff_channel_ids) == [555, 666]
    assert json.loads(db_config.announcement_channel_ids) == [777, 888]

    # 4. Verify GET config returns the updated settings
    response = client.get(f"/api/guild/{guild_id}/audit/config")
    assert response.status_code == 200
    data = response.json()
    assert data["staff_separator_role_id"] == 1234567890
    assert data["staff_channel_ids"] == [555, 666]
    assert data["announcement_channel_ids"] == [777, 888]

    # 5. Mock SecurityRuleEngine.evaluate to verify GET score and GET alerts
    mock_evaluate_val = {
        "score": 92,
        "alerts": [
            {"rule": "Rule 1", "category": "exposure", "severity": "high"},
            {"rule": "Rule 2", "category": "roles", "severity": "medium"},
            {"rule": "Rule 3", "category": "exposure", "severity": "low"},
        ],
    }
    with patch("app.extensions.utilities.sprocket.SecurityRuleEngine.evaluate", return_value=mock_evaluate_val):
        # GET Score
        response = client.get(f"/api/guild/{guild_id}/audit/score")
        assert response.status_code == 200
        score_data = response.json()
        assert score_data["score"] == 92
        assert score_data["severities"]["high"] == 1
        assert score_data["severities"]["medium"] == 1
        assert score_data["severities"]["low"] == 1

        # GET Alerts (all)
        response = client.get(f"/api/guild/{guild_id}/audit/alerts")
        assert response.status_code == 200
        alerts_data = response.json()
        assert len(alerts_data) == 3

        # GET Alerts filtered by category "exposure"
        response = client.get(f"/api/guild/{guild_id}/audit/alerts?category=exposure")
        assert response.status_code == 200
        filtered_data = response.json()
        assert len(filtered_data) == 2
        assert all(a["category"] == "exposure" for a in filtered_data)
