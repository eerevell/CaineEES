"""Execution result critic."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from Caine.core.models import ExecutionResult, Task


@dataclass(slots=True)
class Critic:
    """Validate task results and prevent runaway failure loops."""

    max_consecutive_failures: int
    logger: logging.Logger
    _consecutive_failures: int = field(default=0)

    def evaluate(self, task: Task, result: ExecutionResult) -> bool:
        """Return whether a result is acceptable."""

        if result.success:
            self._consecutive_failures = 0
            return True
        self._consecutive_failures += 1
        self.logger.warning(
            "Task %s rejected: %s; consecutive failures=%s",
            task.id,
            result.message,
            self._consecutive_failures,
        )
        return False

    def should_pause(self) -> bool:
        """Return whether the loop should avoid new risky work."""

        return self._consecutive_failures >= self.max_consecutive_failures

