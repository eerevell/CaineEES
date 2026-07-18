"""Tests for executor and critic."""

from __future__ import annotations

import pytest

from Caine.core.critic import Critic
from Caine.core.executor import Executor
from Caine.core.models import ExecutionResult, Task
from Caine.tests.conftest import make_test_logger


@pytest.mark.asyncio
async def test_executor_dispatches_registered_handler() -> None:
    async def handler(task: Task) -> ExecutionResult:
        return ExecutionResult(task_id=task.id, success=True, message="ok")

    task = Task(kind="custom", payload={})
    executor = Executor(
        logger=make_test_logger(),
        handlers={"custom": handler},
    )

    result = await executor.execute(task)

    assert result.success is True
    assert result.task_id == task.id


def test_critic_pauses_after_failures() -> None:
    task = Task(kind="x", payload={})
    critic = Critic(max_consecutive_failures=2, logger=make_test_logger())

    critic.evaluate(task, ExecutionResult(task.id, False, "bad"))
    critic.evaluate(task, ExecutionResult(task.id, False, "bad"))

    assert critic.should_pause() is True
