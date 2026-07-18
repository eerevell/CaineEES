"""Plugin registry and loading contracts."""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from Caine.core.event_bus import EventBus
from Caine.core.executor import Executor


class CainePlugin(Protocol):
    """Plugin contract."""

    name: str
    permissions: set[str]

    async def on_load(self) -> None:
        """Run after module import."""

    async def on_start(self) -> None:
        """Run when Caine starts."""

    async def on_tick(self) -> None:
        """Run each Caine tick."""

    async def on_stop(self) -> None:
        """Run before shutdown."""

    async def on_unload(self) -> None:
        """Run after stop before plugin removal."""

    def event_subscriptions(self) -> dict[str, str]:
        """Return event name to handler-name mapping."""

    async def register(self, executor: Executor) -> None:
        """Register plugin-provided capabilities."""


@dataclass(slots=True)
class PluginRegistry:
    """Load plugins from configured directories."""

    directories: list[Path]
    logger: logging.Logger
    event_bus: EventBus | None = None
    plugins: list[CainePlugin] = field(default_factory=list)
    permissions: dict[str, set[str]] = field(default_factory=dict)

    async def load(self, executor: Executor) -> None:
        """Load all plugin modules exposing a `plugin` object."""

        for directory in self.directories:
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.py")):
                plugin = self._load_plugin(path)
                if plugin is None:
                    continue
                await self._call(plugin, "on_load")
                await plugin.register(executor)
                self._register_events(plugin)
                self.plugins.append(plugin)
                self.permissions[plugin.name] = set(
                    getattr(plugin, "permissions", set()),
                )
                self.logger.info("Loaded plugin: %s", plugin.name)

    async def start(self) -> None:
        """Start loaded plugins."""

        for plugin in self.plugins:
            await self._call(plugin, "on_start")

    async def tick(self) -> None:
        """Tick loaded plugins."""

        for plugin in self.plugins:
            await self._call(plugin, "on_tick")

    async def stop(self) -> None:
        """Stop loaded plugins."""

        for plugin in reversed(self.plugins):
            await self._call(plugin, "on_stop")
            await self._call(plugin, "on_unload")

    def has_permission(self, plugin_name: str, permission: str) -> bool:
        """Return whether a plugin has a permission."""

        return permission in self.permissions.get(plugin_name, set())

    def _load_plugin(self, path: Path) -> CainePlugin | None:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plugin = getattr(module, "plugin", None)
        if plugin is None:
            self.logger.warning("Plugin file %s has no 'plugin' object", path)
            return None
        return plugin

    def _register_events(self, plugin: CainePlugin) -> None:
        if self.event_bus is None:
            return
        subscriptions = self._subscriptions(plugin)
        for event_name, handler_name in subscriptions.items():
            handler = getattr(plugin, handler_name, None)
            if handler is not None:
                self.event_bus.subscribe(event_name, handler)

    def _subscriptions(self, plugin: CainePlugin) -> dict[str, str]:
        method = getattr(plugin, "event_subscriptions", None)
        if method is None:
            return {}
        subscriptions = method()
        if isinstance(subscriptions, dict):
            return {
                str(key): str(value)
                for key, value in subscriptions.items()
            }
        return {}

    async def _call(self, plugin: CainePlugin, method_name: str) -> None:
        method = getattr(plugin, method_name, None)
        if method is None:
            return
        result = method()
        if hasattr(result, "__await__"):
            await result
