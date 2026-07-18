"""Task planning and priority management."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from Caine.core.models import Goal, SystemState, Task, TaskStatus
from Caine.memory.store import MemoryStore


@dataclass(slots=True)
class Planner:
    """Maintain and prioritize the autonomous task queue."""

    memory: MemoryStore
    logger: logging.Logger
    _queue: list[Task] = field(default_factory=list)

    async def restore(self, queue: list[Task]) -> None:
        """Restore queue from checkpoint and durable memory."""

        self._queue = [
            task for task in queue if task.status == TaskStatus.PENDING
        ]
        for task in await self.memory.list_tasks(TaskStatus.PENDING):
            if all(existing.id != task.id for existing in self._queue):
                self._queue.append(task)
        self._sort()

    async def plan(self, state: SystemState) -> Goal:
        """Create the next goal from current state."""

        if not state.internet_available:
            return Goal(
                description="Restore or tolerate missing internet",
                priority=10,
            )
        if state.disk_percent > 90:
            return Goal(description="Reduce disk pressure", priority=20)
        return Goal(
            description="Continue autonomous maintenance",
            priority=100,
        )

    async def ensure_tasks_for_goal(self, goal: Goal) -> None:
        """Create tasks for a goal when no pending work exists."""

        if self._queue:
            return
        task = Task(
            kind="system_check",
            payload={"goal_id": goal.id, "description": goal.description},
            priority=goal.priority,
        )
        await self.add_task(task)

    async def add_task(self, task: Task) -> None:
        """Add a task to the queue and persist it."""

        self._queue.append(task)
        self._sort()
        await self.memory.save_task(task)

    async def next_task(self) -> Task | None:
        """Pop the highest-priority pending task."""

        self._sort()
        while self._queue:
            task = self._queue.pop(0)
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.RUNNING
                task.attempts += 1
                await self.memory.save_task(task)
                return task
        return None

    async def requeue_or_fail(self, task: Task) -> None:
        """Requeue task until its attempt budget is exhausted."""

        if task.attempts >= task.max_attempts:
            task.status = TaskStatus.FAILED
            self.logger.warning("Task %s exhausted retry budget", task.id)
        else:
            task.status = TaskStatus.PENDING
            self._queue.append(task)
            self._sort()
        await self.memory.save_task(task)

    def snapshot(self) -> list[Task]:
        """Return the current in-memory queue."""

        return list(self._queue)

    def pending_count(self) -> int:
        """Return pending queue length."""

        return len(
            [
                task
                for task in self._queue
                if task.status == TaskStatus.PENDING
            ],
        )

    def _sort(self) -> None:
        self._queue.sort(key=lambda task: (task.priority, task.created_at))
