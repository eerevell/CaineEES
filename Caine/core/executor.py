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

    async def execute(self, task: Task) -> ExecutionResult:
        """Execute a task and return its result."""

        handler = self.handlers.get(task.kind)
        if handler is None:
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


async def system_check_handler(task: Task) -> ExecutionResult:
    """Default minimal task used by the planner."""

    return ExecutionResult(
        task_id=task.id,
        success=True,
        message="System check completed",
        data={"payload": task.payload},
    )

