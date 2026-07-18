"""Repository contracts for persistent memory."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from Caine.core.models import Goal, Task, TaskStatus


class MemoryRepository(Protocol):
    """Persistence contract independent from SQLite."""

    async def open(self) -> None:
        """Open repository resources."""

    async def close(self) -> None:
        """Close repository resources."""

    async def save_task(self, task: Task) -> None:
        """Persist a task."""

    async def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """List persisted tasks."""

    async def save_goal(self, goal: Goal) -> None:
        """Persist a goal."""

    async def remember(
        self,
        category: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Persist structured memory."""

    async def recall(self, category: str, key: str) -> dict[str, Any] | None:
        """Load structured memory."""

    async def record_experience(
        self,
        task_id: str,
        success: bool,
        message: str,
        data: dict[str, Any],
    ) -> None:
        """Persist execution experience."""

    async def persist_checkpoint(
        self,
        path: Path,
        current_goal: Goal | None,
        queue: list[Task],
        planner_state: dict[str, Any] | None = None,
        memory_state: dict[str, Any] | None = None,
    ) -> None:
        """Persist a crash recovery checkpoint."""

    async def load_checkpoint(
        self,
        path: Path,
    ) -> tuple[Goal | None, list[Task], dict[str, Any]]:
        """Load a crash recovery checkpoint."""
