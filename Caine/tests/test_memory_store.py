"""Tests for SQLite memory."""

from __future__ import annotations

import pytest

from Caine.core.models import Goal, Task, TaskStatus
from Caine.memory.store import MemoryStore


@pytest.mark.asyncio
async def test_memory_persists_tasks_and_checkpoint(tmp_path) -> None:
    store = MemoryStore(tmp_path / "data" / "caine.sqlite3")
    await store.open()
    task = Task(kind="system_check", payload={"x": 1}, priority=5)
    goal = Goal(description="test goal", priority=5)

    await store.save_task(task)
    await store.save_goal(goal)
    await store.remember("knowledge", "answer", {"value": 42})
    await store.persist_checkpoint(
        tmp_path / "data" / "checkpoint.json",
        goal,
        [task],
    )

    tasks = await store.list_tasks(TaskStatus.PENDING)
    restored_goal, restored_tasks, metadata = await store.load_checkpoint(
        tmp_path / "data" / "checkpoint.json",
    )
    memory = await store.recall("knowledge", "answer")
    await store.close()

    assert tasks[0].id == task.id
    assert restored_goal is not None
    assert restored_goal.description == "test goal"
    assert restored_tasks[0].id == task.id
    assert "saved_at" in metadata
    assert memory == {"value": 42}
