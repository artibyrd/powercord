import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.common.alchemy import get_session
from app.db.models import DiscordAuditorConfig
from app.extensions.utilities.sprocket import router

pytestmark = pytest.mark.unit

# Initialize test app
app = FastAPI()
app.include_router(router, prefix="/utilities")


@pytest.fixture
def client(session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@patch("app.extensions.utilities.sprocket.SecurityRuleEngine.evaluate")
def test_get_audit_score(mock_evaluate, client):
    guild_id = 100001
    mock_evaluate.return_value = {
        "score": 85,
        "alerts": [
            {"severity": "high"},
            {"severity": "medium"},
            {"severity": "low"},
            {"severity": "high"},
        ],
    }

    response = client.get(f"/utilities/api/guild/{guild_id}/audit/score")
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 85
    assert data["severities"]["high"] == 2
    assert data["severities"]["medium"] == 1
    assert data["severities"]["low"] == 1


@patch("app.extensions.utilities.sprocket.SecurityRuleEngine.evaluate")
def test_get_audit_alerts(mock_evaluate, client):
    guild_id = 100002
    alerts = [
        {"rule": "Rule A", "category": "exposure", "severity": "high"},
        {"rule": "Rule B", "category": "roles", "severity": "low"},
    ]
    mock_evaluate.return_value = {
        "score": 85,
        "alerts": alerts,
    }

    # Test get all alerts
    response = client.get(f"/utilities/api/guild/{guild_id}/audit/alerts")
    assert response.status_code == 200
    assert response.json() == alerts

    # Test get filtered by category
    response = client.get(f"/utilities/api/guild/{guild_id}/audit/alerts?category=exposure")
    assert response.status_code == 200
    assert response.json() == [alerts[0]]


def test_get_auditor_config_empty(client):
    guild_id = 100003
    response = client.get(f"/utilities/api/guild/{guild_id}/audit/config")
    assert response.status_code == 200
    data = response.json()
    assert data["staff_separator_role_id"] is None
    assert data["staff_channel_ids"] == []
    assert data["announcement_channel_ids"] == []


def test_get_auditor_config_existing(client, session):
    guild_id = 100004
    config = DiscordAuditorConfig(
        guild_id=guild_id,
        staff_separator_role_id=111,
        staff_channel_ids="[222, 333]",
        announcement_channel_ids="[444]",
    )
    session.add(config)
    session.commit()

    response = client.get(f"/utilities/api/guild/{guild_id}/audit/config")
    assert response.status_code == 200
    data = response.json()
    assert data["staff_separator_role_id"] == 111
    assert data["staff_channel_ids"] == [222, 333]
    assert data["announcement_channel_ids"] == [444]


def test_post_auditor_config_new(client, session):
    guild_id = 100005
    payload = {
        "staff_separator_role_id": 999,
        "staff_channel_ids": [888, 777],
        "announcement_channel_ids": [666],
    }
    response = client.post(f"/utilities/api/guild/{guild_id}/audit/config", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["staff_separator_role_id"] == 999
    assert data["staff_channel_ids"] == [888, 777]
    assert data["announcement_channel_ids"] == [666]

    # Verify saved to database
    session.expire_all()
    db_config = session.get(DiscordAuditorConfig, guild_id)
    assert db_config is not None
    assert db_config.staff_separator_role_id == 999
    assert json.loads(db_config.staff_channel_ids) == [888, 777]
    assert json.loads(db_config.announcement_channel_ids) == [666]


def test_post_auditor_config_update(client, session):
    guild_id = 100006
    config = DiscordAuditorConfig(
        guild_id=guild_id,
        staff_separator_role_id=111,
        staff_channel_ids="[222]",
        announcement_channel_ids="[333]",
    )
    session.add(config)
    session.commit()

    payload = {
        "staff_separator_role_id": 555,
        "staff_channel_ids": [444],
        "announcement_channel_ids": [222, 111],
    }
    response = client.post(f"/utilities/api/guild/{guild_id}/audit/config", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["staff_separator_role_id"] == 555
    assert data["staff_channel_ids"] == [444]
    assert data["announcement_channel_ids"] == [222, 111]

    # Verify database was updated
    session.expire_all()
    db_config = session.get(DiscordAuditorConfig, guild_id)
    assert db_config.staff_separator_role_id == 555
    assert json.loads(db_config.staff_channel_ids) == [444]
    assert json.loads(db_config.announcement_channel_ids) == [222, 111]


def test_post_auditor_config_partial_update(client, session):
    guild_id = 100007
    config = DiscordAuditorConfig(
        guild_id=guild_id,
        staff_separator_role_id=111,
        staff_channel_ids="[222]",
        announcement_channel_ids="[333]",
    )
    session.add(config)
    session.commit()

    # staff_separator_role_id is omitted from payload
    payload = {
        "staff_channel_ids": [444],
        "announcement_channel_ids": [222, 111],
    }
    response = client.post(f"/utilities/api/guild/{guild_id}/audit/config", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["staff_separator_role_id"] == 111  # Preserved!
    assert data["staff_channel_ids"] == [444]
    assert data["announcement_channel_ids"] == [222, 111]

    # Verify database was updated and role ID preserved
    session.expire_all()
    db_config = session.get(DiscordAuditorConfig, guild_id)
    assert db_config.staff_separator_role_id == 111  # Preserved!
    assert json.loads(db_config.staff_channel_ids) == [444]
    assert json.loads(db_config.announcement_channel_ids) == [222, 111]
