"""Tests for reasoning and scheduling."""

from __future__ import annotations

import pytest

from Caine.core.reasoning import Reasoning
from Caine.core.scheduler import PeriodicJob, Scheduler
from Caine.tests.conftest import make_settings, make_test_logger


class FakeRemote:
    async def reason(self, prompt, context):
        return None


@pytest.mark.asyncio
async def test_reasoning_falls_back_to_local(tmp_path) -> None:
    settings = make_settings(tmp_path)
    reasoning = Reasoning(settings.reasoning, FakeRemote(), make_test_logger())

    decision = await reasoning.decide(
        "complex prompt text",
        {"pending_tasks": 1},
    )

    assert decision == "process_pending_task"


@pytest.mark.asyncio
async def test_scheduler_runs_due_job() -> None:
    calls: list[str] = []

    async def action() -> None:
        calls.append("ran")

    scheduler = Scheduler()
    scheduler.add_job(PeriodicJob("job", 0, action))

    executed = await scheduler.tick()

    assert executed == ["job"]
    assert calls == ["ran"]
