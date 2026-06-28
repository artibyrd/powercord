import hashlib
import json
from unittest.mock import AsyncMock, patch

import pytest
from fasthtml.common import to_xml


@pytest.mark.unit
@pytest.mark.asyncio
async def test_profile_client_keys_non_admin(session):
    """Verify that when a user is not a global admin, the key section displays restricted notice."""
    from app.main_ui import _render_client_keys

    # User ID 12345, not a global admin
    sess = {"auth": {"id": "12345"}}

    with (
        patch("app.ui.helpers.is_dashboard_admin", return_value=False),
        patch("app.common.alchemy.init_connection_engine", return_value=session.get_bind()),
    ):
        res = await _render_client_keys(sess)
        html = to_xml(res)

        assert "Companion Client Keys" in html
        assert "restricted to global administrators" in html
        assert "Generate Client Key" not in html
        assert "Select Scope" not in html


@pytest.mark.unit
@pytest.mark.asyncio
async def test_profile_client_keys_admin(session):
    """Verify that a global admin sees key table with masked keys and generation form."""
    from app.db.models import ApiKey
    from app.main_ui import _render_client_keys

    # Insert a client key for the user
    user_id = 99999
    prefix = f"client_{user_id}_"
    api_key = ApiKey(
        key_hash="dummyhash",
        name=f"{prefix}key1",
        scopes=json.dumps(["global.admin"]),
        is_active=True,
        key_type="global",
    )
    session.add(api_key)
    session.commit()

    sess = {"auth": {"id": str(user_id)}}

    with (
        patch("app.ui.helpers.is_dashboard_admin", return_value=True),
        patch("app.common.alchemy.init_connection_engine", return_value=session.get_bind()),
    ):
        res = await _render_client_keys(sess)
        html = to_xml(res)

        assert "Companion Client Keys" in html
        assert "••••••••••••••••" in html  # masked key
        assert "dummyhash" not in html  # no hash displayed
        assert "Generate Client Key" in html
        assert "global.admin" in html
        assert "global.utilities.admin" in html  # dynamically populated from GadgetInspector


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_client_key_route_admin(session):
    """Verify global admin client key generation hashes key and stores it, returning raw key once."""
    from sqlmodel import select

    from app.db.models import ApiKey
    from app.main_ui import generate_client_key_route

    user_id = 88888
    sess = {"auth": {"id": str(user_id)}}

    mock_req = AsyncMock()
    mock_req.form.return_value = {"scope": "global.admin"}

    with (
        patch("app.ui.helpers.is_dashboard_admin", return_value=True),
        patch("app.common.alchemy.init_connection_engine", return_value=session.get_bind()),
    ):
        await generate_client_key_route(mock_req, sess)

        # Retrieve the key from DB
        prefix = f"client_{user_id}_"
        keys = session.exec(select(ApiKey).where(ApiKey.name.startswith(prefix))).all()
        assert len(keys) == 1
        assert keys[0].key_type == "global"
        assert json.loads(keys[0].scopes) == ["global.admin"]

        # Verify toast success message contains the raw key
        toasts = sess.get("toasts", [])
        assert len(toasts) == 1
        toast_msg = toasts[0][0]
        assert "New client key generated: pc_" in toast_msg

        # Verify the key in toast is hashed correctly in DB
        raw_key = toast_msg.split("generated: ")[1].split(" (")[0]
        expected_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        assert keys[0].key_hash == expected_hash


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_api_key_toggle_route(session):
    """Verify that toggle route revokes and reactivates API keys correctly."""
    from sqlmodel import Session

    from app.db.models import ApiKey
    from app.main_ui import toggle_api_key_route

    # Insert a key
    key = ApiKey(
        key_hash="somehash",
        name="test-api-key",
        scopes=json.dumps(["global.user"]),
        is_active=True,
        key_type="global",
    )
    session.add(key)
    session.commit()

    key_id = key.id
    print("DEBUG: key_id =", key_id)
    with Session(session.get_bind()) as verify_sess:
        print("DEBUG: Before close, key exists:", verify_sess.get(ApiKey, key_id))
    session.close()  # Release locks!
    with Session(session.get_bind()) as verify_sess:
        print("DEBUG: After close, key exists:", verify_sess.get(ApiKey, key_id))

    sess = {"auth": {"id": "11111"}}

    # 1. Revoke the key
    mock_req = AsyncMock()
    mock_req.form.return_value = {"key_id": str(key_id), "action": "revoke"}

    with (
        patch("app.ui.helpers.is_dashboard_admin", return_value=True),
        patch("app.common.alchemy.init_connection_engine", return_value=session.get_bind()),
    ):
        await toggle_api_key_route(mock_req, sess)

        # Verify in DB
        with Session(session.get_bind()) as verify_sess:
            updated_key = verify_sess.get(ApiKey, key_id)
            print("DEBUG: After revoke, key exists:", updated_key)
            assert updated_key.is_active is False

        # 2. Reactivate the key
        mock_req.form.return_value = {"key_id": str(key_id), "action": "reactivate"}
        await toggle_api_key_route(mock_req, sess)

        # Verify in DB
        with Session(session.get_bind()) as verify_sess:
            re_updated_key = verify_sess.get(ApiKey, key_id)
            assert re_updated_key.is_active is True
