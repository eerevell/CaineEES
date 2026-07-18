"""Tests for the Brain coordinator."""

from __future__ import annotations

import pytest

from Caine.core.brain import Brain
from Caine.core.critic import Critic
from Caine.core.event_bus import EventBus
from Caine.core.executor import Executor, system_check_handler
from Caine.core.health import HealthManager
from Caine.core.models import SystemState
from Caine.core.observer import Observer
from Caine.core.planner import Planner
from Caine.core.reasoning import Reasoning
from Caine.core.scheduler import Scheduler
from Caine.core.shutdown import ShutdownManager
from Caine.core.updater import AsyncCommandRunner, Updater
from Caine.core.watchdog import Watchdog
from Caine.memory.store import MemoryStore
from Caine.network.compute_node import ComputeNodeClient
from Caine.tests.conftest import make_settings, make_test_logger


class NoopRemote:
    async def reason(self, prompt, context):
        return None


class FakeObserver(Observer):
    async def observe(self) -> SystemState:
        return SystemState(1, 2, 3, None, True, {})


@pytest.mark.asyncio
async def test_brain_runs_one_cycle(tmp_path) -> None:
    settings = make_settings(tmp_path)
    store = MemoryStore(settings.memory.database_path)
    await store.open()
    logger = make_test_logger()
    event_bus = EventBus(logger)
    compute_node = ComputeNodeClient(
        settings.network,
        settings.reasoning,
        logger,
        event_bus,
    )
    brain = Brain(
        settings=settings,
        memory=store,
        planner=Planner(store, logger),
        observer=FakeObserver("127.0.0.1", 9, 0.01),
        executor=Executor(logger, {"system_check": system_check_handler}),
        critic=Critic(2, logger),
        reasoning=Reasoning(settings.reasoning, NoopRemote(), logger),
        scheduler=Scheduler(),
        updater=Updater(settings.update, logger, AsyncCommandRunner()),
        shutdown=ShutdownManager(logger),
        event_bus=event_bus,
        health=HealthManager(logger),
        watchdog=Watchdog(5.0, logger),
        compute_node=compute_node,
        logger=logger,
    )
    await brain.initialize(None, [])

    await brain.run_once()
    tasks = await store.list_tasks()
    await store.close()

    assert brain.current_goal is not None
    assert tasks[0].status.value == "succeeded"
