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
    permissions = {"executor.register"}
    events = []

    async def on_load(self):
        self.events.append("load")

    async def on_start(self):
        self.events.append("start")

    async def on_tick(self):
        self.events.append("tick")

    async def on_stop(self):
        self.events.append("stop")

    async def on_unload(self):
        self.events.append("unload")

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
    await registry.start()
    await registry.tick()
    await registry.stop()

    assert "plugin_task" in executor.handlers
    assert registry.plugins[0].name == "sample"
    assert registry.has_permission("sample", "executor.register") is True
    assert registry.plugins[0].events == [
        "load",
        "start",
        "tick",
        "stop",
        "unload",
    ]


@pytest.mark.asyncio
async def test_remote_reasoning_returns_none_when_unavailable() -> None:
    client = RemoteReasoningClient(
        api_url="http://127.0.0.1:1/reason",
        timeout_seconds=0.01,
        logger=logging.getLogger("test"),
    )

    answer = await client.reason("prompt", {})

    assert answer is None
