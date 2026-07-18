"""Tests for plugins and network clients."""

from __future__ import annotations

import logging

import pytest

from Caine.core.executor import Executor
from Caine.network.remote_reasoning import RemoteReasoningClient
from Caine.plugins.registry import PluginRegistry


@pytest.mark.asyncio
async def test_plugin_registry_loads_plugin(tmp_path) -> None:
    plugin_file = tmp_path / "sample_plugin.py"
    plugin_file.write_text(
        """
from Caine.core.models import ExecutionResult

class SamplePlugin:
    name = "sample"

    async def register(self, executor):
        async def handler(task):
            return ExecutionResult(task.id, True, "plugin ok")
        executor.handlers["plugin_task"] = handler

plugin = SamplePlugin()
""",
        encoding="utf-8",
    )
    executor = Executor(logging.getLogger("test"), {})
    registry = PluginRegistry([tmp_path], logging.getLogger("test"))

    await registry.load(executor)

    assert "plugin_task" in executor.handlers
    assert registry.plugins[0].name == "sample"


@pytest.mark.asyncio
async def test_remote_reasoning_returns_none_when_unavailable() -> None:
    client = RemoteReasoningClient(
        api_url="http://127.0.0.1:1/reason",
        timeout_seconds=0.01,
        logger=logging.getLogger("test"),
    )

    answer = await client.reason("prompt", {})

    assert answer is None
