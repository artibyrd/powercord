from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_sys_exit():
    with patch("sys.exit", side_effect=SystemExit) as mock_exit:
        yield mock_exit


@pytest.fixture
def mock_session():
    with (
        patch("app.db.manage_api_keys.Session") as mock_session_cls,
        patch("app.db.manage_api_keys.init_connection_engine"),
    ):
        session_mock = MagicMock()
        mock_session_cls.return_value = session_mock
        session_mock.__enter__.return_value = session_mock
        yield session_mock


def test_add_api_key_new_key(mock_session):
    from app.db.manage_api_keys import add_api_key

    mock_session.exec.return_value.first.return_value = None

    with patch("app.db.manage_api_keys.secrets.token_urlsafe", return_value="12345"):
        add_api_key(name="Test", scopes='["global"]')

    # Verify api key added
    mock_session.add.assert_called_once()
    added_key = mock_session.add.call_args[0][0]
    assert added_key.name == "Test"
    assert added_key.key == "pc_12345"
    assert added_key.scopes == '["global"]'
    assert added_key.is_active is True
    mock_session.commit.assert_called_once()


def test_add_api_key_specific_key(mock_session):
    from app.db.manage_api_keys import add_api_key

    mock_session.exec.return_value.first.return_value = None

    add_api_key(name="Test Legacy", scopes='["global"]', specific_key="legacy-12345")

    mock_session.add.assert_called_once()
    added_key = mock_session.add.call_args[0][0]
    assert added_key.name == "Test Legacy"
    assert added_key.key == "legacy-12345"
    assert added_key.scopes == '["global"]'
    mock_session.commit.assert_called_once()


def test_add_api_key_existing_name(mock_session, mock_sys_exit):
    from app.db.manage_api_keys import add_api_key

    # Simulate an existing key
    mock_session.exec.return_value.first.return_value = "ExistingKey"

    with pytest.raises(SystemExit):
        add_api_key(name="Existing", scopes='["global"]')

    mock_sys_exit.assert_called_once_with(1)
    mock_session.add.assert_not_called()
