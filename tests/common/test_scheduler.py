"""Unit tests for the Framework-Level ActionScheduler."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.common.extension_loader import GadgetInspector
from app.common.scheduler import ActionScheduler, ScheduledAction, get_action_scheduler, register_scheduled_action

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_scheduler():
    """Ensure clean scheduler state before each test."""
    scheduler = get_action_scheduler()
    scheduler.shutdown()
    scheduler._registered_actions.clear()
    yield
    scheduler.shutdown()
    scheduler._registered_actions.clear()


def test_action_scheduler_singleton():
    """Verify ActionScheduler is a singleton."""
    s1 = ActionScheduler()
    s2 = get_action_scheduler()
    assert s1 is s2


def test_register_action_instance():
    """Verify registering a ScheduledAction instance."""
    scheduler = get_action_scheduler()
    dummy_func = MagicMock()

    action = ScheduledAction(
        action_id="test_action",
        func=dummy_func,
        trigger="interval",
        name="Test Action",
        description="A test scheduled action",
        trigger_args={"minutes": 10},
    )
    scheduler.register_action(action)

    assert "test_action" in scheduler._registered_actions
    registered = scheduler._registered_actions["test_action"]
    assert registered.name == "Test Action"
    assert registered.trigger == "interval"
    assert registered.trigger_args == {"minutes": 10}


def test_register_action_kwargs():
    """Verify registering via keyword arguments and helper function."""
    dummy_func = MagicMock()
    register_scheduled_action(
        action_id="kwarg_action",
        func=dummy_func,
        trigger="cron",
        hour=3,
        minute=0,
        name="Kwarg Action",
    )

    scheduler = get_action_scheduler()
    assert "kwarg_action" in scheduler._registered_actions
    registered = scheduler._registered_actions["kwarg_action"]
    assert registered.trigger == "cron"
    assert registered.trigger_args == {"hour": 3, "minute": 0}


def test_sync_job_execution_wrapper():
    """Verify synchronous jobs execute with logging and duration tracking."""
    scheduler = get_action_scheduler()
    dummy_func = MagicMock(return_value="success_result")

    action = ScheduledAction(
        action_id="sync_test",
        func=dummy_func,
        trigger="interval",
        name="Sync Test",
    )
    wrapped = scheduler._wrap_job(action)

    with patch("app.common.scheduler.logger") as mock_logger:
        result = wrapped("arg1", kwarg="kw1")
        assert result == "success_result"
        dummy_func.assert_called_once_with("arg1", kwarg="kw1")
        assert any(
            "Completed scheduled action" in str(call) and "Sync Test" in str(call)
            for call in mock_logger.info.call_args_list
        )


@pytest.mark.asyncio
async def test_async_job_execution_wrapper():
    """Verify asynchronous jobs execute with logging and duration tracking."""
    scheduler = get_action_scheduler()

    async def async_dummy():
        await asyncio.sleep(0.01)
        return "async_result"

    action = ScheduledAction(
        action_id="async_test",
        func=async_dummy,
        trigger="interval",
        name="Async Test",
    )
    wrapped = scheduler._wrap_job(action)

    with patch("app.common.scheduler.logger") as mock_logger:
        result = await wrapped()
        assert result == "async_result"
        assert any(
            "Completed scheduled action" in str(call) and "Async Test" in str(call)
            for call in mock_logger.info.call_args_list
        )


def test_job_execution_error_handling():
    """Verify job exceptions are caught, logged, and do not crash the scheduler."""
    scheduler = get_action_scheduler()

    def failing_func():
        raise RuntimeError("Simulated action failure")

    action = ScheduledAction(
        action_id="failing_test",
        func=failing_func,
        trigger="interval",
        name="Failing Test",
    )
    wrapped = scheduler._wrap_job(action)

    with patch("app.common.scheduler.logger") as mock_logger:
        res = wrapped()
        assert res is None
        mock_logger.exception.assert_called_once()


def test_get_scheduled_actions_status():
    """Verify get_scheduled_actions returns detailed status list."""
    scheduler = get_action_scheduler()
    dummy_func = MagicMock()

    scheduler.register_action(
        action_id="status_action",
        func=dummy_func,
        trigger="interval",
        name="Status Action",
        description="Testing status report",
        minutes=5,
    )

    actions = scheduler.get_scheduled_actions()
    assert len(actions) == 1
    assert actions[0]["action_id"] == "status_action"
    assert actions[0]["name"] == "Status Action"
    assert actions[0]["trigger"] == "interval"
    assert actions[0]["trigger_args"] == {"minutes": 5}
    assert actions[0]["enabled"] is True


def test_gadget_inspector_discovers_actions(tmp_path):
    """Verify GadgetInspector finds actions.py across extensions."""
    inspector = GadgetInspector()
    actions = inspector.inspect_scheduled_actions()
    # If midi_library has actions.py, it should be in the report
    if (inspector.extensions_dir / "midi_library" / "actions.py").exists():
        assert "midi_library" in actions
        action_ids = [a.action_id for a in actions["midi_library"]]
        assert "midi_health_log_scan" in action_ids
        assert "midi_health_full_scan" in action_ids
