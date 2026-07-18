"""Tests for startup and shutdown managers."""

from __future__ import annotations

import pytest

from Caine.core.models import Goal, Task
from Caine.core.shutdown import ShutdownManager
from Caine.core.startup import StartupManager
from Caine.memory.store import MemoryStore
from Caine.tests.conftest import make_settings, make_test_logger


@pytest.mark.asyncio
async def test_startup_restores_checkpoint(tmp_path) -> None:
    settings = make_settings(tmp_path)
    store = MemoryStore(settings.memory.database_path)
    await store.open()
    goal = Goal("restore")
    task = Task("system_check", {})
    await store.persist_checkpoint(
        settings.memory.checkpoint_path,
        goal,
        [task],
    )
    await store.close()

    store = MemoryStore(settings.memory.database_path)
    startup = StartupManager(settings, store, make_test_logger())
    restored_goal, queue = await startup.initialize()
    await store.close()

    assert restored_goal is not None
    assert restored_goal.description == "restore"
    assert queue[0].id == task.id


@pytest.mark.asyncio
async def test_shutdown_runs_callbacks() -> None:
    manager = ShutdownManager(make_test_logger())
    reasons: list[str] = []

    async def callback(reason: str) -> None:
        reasons.append(reason)

    manager.register(callback)
    manager.request_shutdown("SIGTERM")
    await manager.cleanup()

    assert manager.requested is True
    assert reasons == ["SIGTERM"]
