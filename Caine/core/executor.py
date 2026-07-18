"""Task execution engine."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from Caine.core.models import ExecutionResult, Task

TaskHandler = Callable[[Task], Awaitable[ExecutionResult]]


@dataclass(slots=True)
class Executor:
    """Execute tasks through registered async handlers."""

    logger: logging.Logger
    handlers: dict[str, TaskHandler]
    active_tasks: set[str]

    def __init__(
        self,
        logger: logging.Logger,
        handlers: dict[str, TaskHandler],
    ) -> None:
        self.logger = logger
        self.handlers = handlers
        self.active_tasks = set()

    async def execute(self, task: Task) -> ExecutionResult:
        """Execute a task and return its result."""

        self.active_tasks.add(task.id)
        handler = self.handlers.get(task.kind)
        if handler is None:
            self.active_tasks.discard(task.id)
            return ExecutionResult(
                task_id=task.id,
                success=False,
                message=f"No handler registered for task kind '{task.kind}'",
            )
        try:
            return await handler(task)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.logger.exception("Task %s failed unexpectedly", task.id)
            return ExecutionResult(
                task_id=task.id,
                success=False,
                message=str(exc),
            )
        finally:
            self.active_tasks.discard(task.id)

    def has_active_tasks(self) -> bool:
        """Return whether tasks are currently running."""

        return bool(self.active_tasks)


async def system_check_handler(task: Task) -> ExecutionResult:
    """Default minimal task used by the planner."""

    return ExecutionResult(
        task_id=task.id,
        success=True,
        message="System check completed",
        data={"payload": task.payload},
    )
