"""Task planning and priority management."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from Caine.core.models import Goal, SystemState, Task, TaskStatus
from Caine.memory.repository import MemoryRepository


@dataclass(slots=True)
class Planner:
    """Maintain and prioritize the autonomous task queue."""

    memory: MemoryRepository
    logger: logging.Logger
    _queue: list[Task] = field(default_factory=list)
    _completed_task_ids: set[str] = field(default_factory=set)

    async def restore(self, queue: list[Task]) -> None:
        """Restore queue from checkpoint and durable memory."""

        self._queue = [
            task for task in queue if task.status == TaskStatus.PENDING
        ]
        for task in await self.memory.list_tasks(TaskStatus.PENDING):
            if all(existing.id != task.id for existing in self._queue):
                self._queue.append(task)
        self._completed_task_ids = {
            task.id
            for task in await self.memory.list_tasks(TaskStatus.SUCCEEDED)
        }
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

    async def cancel_task(self, task_id: str, reason: str) -> bool:
        """Cancel a queued task."""

        for task in self._queue:
            if task.id != task_id:
                continue
            task.status = TaskStatus.CANCELLED
            task.cancelled_reason = reason
            task.updated_at = datetime.now(UTC)
            await self.memory.save_task(task)
            self._queue = [item for item in self._queue if item.id != task_id]
            return True
        return False

    async def next_task(self) -> Task | None:
        """Pop the highest-priority runnable task."""

        self._sort()
        for index, task in enumerate(list(self._queue)):
            if not self._is_runnable(task):
                continue
            self._queue.pop(index)
            task.status = TaskStatus.RUNNING
            task.attempts += 1
            task.updated_at = datetime.now(UTC)
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
            task.updated_at = datetime.now(UTC)
            self._queue.append(task)
            self._sort()
        await self.memory.save_task(task)

    async def complete_successfully(self, task: Task) -> None:
        """Mark a task as succeeded and reschedule recurring work."""

        task.status = TaskStatus.SUCCEEDED
        task.updated_at = datetime.now(UTC)
        self._completed_task_ids.add(task.id)
        await self.memory.save_task(task)
        if task.repeat_interval_seconds is None:
            return
        repeated = Task(
            kind=task.kind,
            payload=dict(task.payload),
            priority=task.priority,
            dependencies=list(task.dependencies),
            not_before=datetime.now(UTC)
            + timedelta(seconds=task.repeat_interval_seconds),
            repeat_interval_seconds=task.repeat_interval_seconds,
        )
        await self.add_task(repeated)

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

    def planner_state(self) -> dict[str, object]:
        """Return checkpoint-friendly planner state."""

        return {
            "queue_size": len(self._queue),
            "pending_count": self.pending_count(),
            "completed_task_count": len(self._completed_task_ids),
            "oldest_task_id": self._queue[0].id if self._queue else None,
        }

    def _is_runnable(self, task: Task) -> bool:
        now = datetime.now(UTC)
        if task.status != TaskStatus.PENDING:
            return False
        if task.not_before is not None and task.not_before > now:
            return False
        if task.deadline is not None and task.deadline < now:
            task.status = TaskStatus.FAILED
            task.cancelled_reason = "deadline missed"
            return False
        return all(
            dependency in self._completed_task_ids
            for dependency in task.dependencies
        )

    def _sort(self) -> None:
        self._queue.sort(
            key=lambda task: (
                task.priority,
                task.not_before or task.created_at,
                task.deadline or datetime.max.replace(tzinfo=UTC),
                task.created_at,
            ),
        )
