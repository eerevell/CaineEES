"""Tests for task planning."""

from __future__ import annotations

import pytest

from Caine.core.models import SystemState, Task, TaskStatus
from Caine.core.planner import Planner
from Caine.memory.store import MemoryStore
from Caine.tests.conftest import make_test_logger


@pytest.mark.asyncio
async def test_planner_prioritizes_and_retries(tmp_path) -> None:
    store = MemoryStore(tmp_path / "caine.sqlite3")
    await store.open()
    planner = Planner(memory=store, logger=make_test_logger())
    await planner.restore([])

    low = Task(kind="system_check", payload={}, priority=50)
    high = Task(kind="system_check", payload={}, priority=1)
    await planner.add_task(low)
    await planner.add_task(high)

    next_task = await planner.next_task()
    assert next_task is not None
    assert next_task.id == high.id

    await planner.requeue_or_fail(next_task)
    assert planner.pending_count() == 2
    await store.close()


@pytest.mark.asyncio
async def test_planner_selects_goal_for_disk_pressure(tmp_path) -> None:
    store = MemoryStore(tmp_path / "caine.sqlite3")
    await store.open()
    planner = Planner(memory=store, logger=make_test_logger())
    state = SystemState(1, 2, 95, None, True, {})

    goal = await planner.plan(state)
    await store.close()

    assert "disk" in goal.description.lower()
