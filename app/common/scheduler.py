"""Framework-level ActionScheduler for Powercord.

Provides a unified scheduling engine using APScheduler for periodic tasks,
background maintenance, and extension-registered cron actions.
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


@dataclass
class ScheduledAction:
    """Configuration for a scheduled action."""

    action_id: str
    func: Callable[..., Any]
    trigger: str  # "cron", "interval", "date"
    name: str = ""
    description: str = ""
    trigger_args: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.action_id


class ActionScheduler:
    """Central singleton managing scheduled tasks and background cron jobs."""

    _instance: ActionScheduler | None = None
    _scheduler: AsyncIOScheduler | None = None
    _registered_actions: dict[str, ScheduledAction] = {}

    def __new__(cls) -> ActionScheduler:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registered_actions = {}
            cls._instance._scheduler = None
        return cls._instance

    @property
    def scheduler(self) -> AsyncIOScheduler:
        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler()
        return self._scheduler

    def register_action(
        self,
        action: ScheduledAction | None = None,
        *,
        action_id: str | None = None,
        func: Callable[..., Any] | None = None,
        trigger: str = "interval",
        name: str = "",
        description: str = "",
        enabled: bool = True,
        **trigger_args: Any,
    ) -> None:
        """Register a scheduled action with the scheduler.

        Can be called with a ScheduledAction instance or individual kwargs.
        """
        if action is not None:
            act = action
        elif action_id and func:
            act = ScheduledAction(
                action_id=action_id,
                func=func,
                trigger=trigger,
                name=name or action_id,
                description=description,
                trigger_args=trigger_args,
                enabled=enabled,
            )
        else:
            raise ValueError("Either an action instance or action_id and func must be provided.")

        self._registered_actions[act.action_id] = act
        logger.info(
            "Registered scheduled action '%s' (trigger=%s, args=%s).", act.action_id, act.trigger, act.trigger_args
        )

        # If scheduler is already running and action is enabled, schedule immediately
        if self._scheduler and self._scheduler.running and act.enabled:
            self._schedule_job(act)

    def _wrap_job(self, act: ScheduledAction) -> Callable[..., Any]:
        """Wrap an action function with execution logging and error handling."""

        if inspect.iscoroutinefunction(act.func):

            @functools.wraps(act.func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                logger.info("Starting scheduled action: %s (%s)", act.name, act.action_id)
                try:
                    res = await act.func(*args, **kwargs)
                    duration = time.time() - start_time
                    logger.info(
                        "Completed scheduled action: %s in %.2fs",
                        act.name,
                        duration,
                        extra={
                            "json_fields": {
                                "event": "scheduled_action_completed",
                                "action_id": act.action_id,
                                "duration_seconds": duration,
                                "status": "success",
                            }
                        },
                    )
                    return res
                except Exception as e:
                    duration = time.time() - start_time
                    logger.exception(
                        "Failed scheduled action: %s after %.2fs: %s",
                        act.name,
                        duration,
                        e,
                        extra={
                            "json_fields": {
                                "event": "scheduled_action_failed",
                                "action_id": act.action_id,
                                "duration_seconds": duration,
                                "status": "error",
                                "error": str(e),
                            }
                        },
                    )

            return async_wrapper

        else:

            @functools.wraps(act.func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                logger.info("Starting scheduled action: %s (%s)", act.name, act.action_id)
                try:
                    res = act.func(*args, **kwargs)
                    duration = time.time() - start_time
                    logger.info(
                        "Completed scheduled action: %s in %.2fs",
                        act.name,
                        duration,
                        extra={
                            "json_fields": {
                                "event": "scheduled_action_completed",
                                "action_id": act.action_id,
                                "duration_seconds": duration,
                                "status": "success",
                            }
                        },
                    )
                    return res
                except Exception as e:
                    duration = time.time() - start_time
                    logger.exception(
                        "Failed scheduled action: %s after %.2fs: %s",
                        act.name,
                        duration,
                        e,
                        extra={
                            "json_fields": {
                                "event": "scheduled_action_failed",
                                "action_id": act.action_id,
                                "duration_seconds": duration,
                                "status": "error",
                                "error": str(e),
                            }
                        },
                    )

            return sync_wrapper

    def _schedule_job(self, act: ScheduledAction) -> None:
        """Add the job to the underlying APScheduler instance."""
        if not self._scheduler:
            return

        wrapped_func = self._wrap_job(act)
        try:
            self._scheduler.add_job(
                wrapped_func,
                trigger=act.trigger,
                id=act.action_id,
                name=act.name,
                replace_existing=True,
                **act.trigger_args,
            )
            logger.info("Scheduled job '%s' with trigger '%s'.", act.action_id, act.trigger)
        except Exception as e:
            logger.exception("Failed to schedule job '%s': %s", act.action_id, e)

    def start(self) -> None:
        """Start the scheduler and schedule all registered actions."""
        sched = self.scheduler
        if not sched.running:
            for act in self._registered_actions.values():
                if act.enabled:
                    self._schedule_job(act)
            sched.start()
            logger.info("ActionScheduler started with %d active jobs.", len(sched.get_jobs()))

    def shutdown(self, wait: bool = False) -> None:
        """Stop the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=wait)
            self._scheduler = None
            logger.info("ActionScheduler stopped.")

    def get_scheduled_actions(self) -> list[dict[str, Any]]:
        """Return status information for all registered actions."""
        jobs_map = {
            job.id: job for job in (self._scheduler.get_jobs() if self._scheduler and self._scheduler.running else [])
        }
        result = []
        for action_id, act in self._registered_actions.items():
            job = jobs_map.get(action_id)
            result.append(
                {
                    "action_id": act.action_id,
                    "name": act.name,
                    "description": act.description,
                    "trigger": act.trigger,
                    "trigger_args": act.trigger_args,
                    "enabled": act.enabled,
                    "is_scheduled": job is not None,
                    "next_run_time": job.next_run_time.isoformat() if job and job.next_run_time else None,
                }
            )
        return result


# Module-level helper functions for convenient access
_default_scheduler = ActionScheduler()


def register_scheduled_action(
    action: ScheduledAction | None = None,
    *,
    action_id: str | None = None,
    func: Callable[..., Any] | None = None,
    trigger: str = "interval",
    name: str = "",
    description: str = "",
    enabled: bool = True,
    **trigger_args: Any,
) -> None:
    """Module-level shortcut to register a scheduled action."""
    _default_scheduler.register_action(
        action=action,
        action_id=action_id,
        func=func,
        trigger=trigger,
        name=name,
        description=description,
        enabled=enabled,
        **trigger_args,
    )


def get_action_scheduler() -> ActionScheduler:
    """Return the global ActionScheduler instance."""
    return _default_scheduler
