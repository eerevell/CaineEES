"""Plugin registry and loading contracts."""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from Caine.core.executor import Executor


class CainePlugin(Protocol):
    """Plugin contract."""

    name: str

    async def register(self, executor: Executor) -> None:
        """Register plugin-provided capabilities."""


@dataclass(slots=True)
class PluginRegistry:
    """Load plugins from configured directories."""

    directories: list[Path]
    logger: logging.Logger
    plugins: list[CainePlugin] = field(default_factory=list)

    async def load(self, executor: Executor) -> None:
        """Load all plugin modules exposing a `plugin` object."""

        for directory in self.directories:
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.py")):
                plugin = self._load_plugin(path)
                if plugin is None:
                    continue
                await plugin.register(executor)
                self.plugins.append(plugin)
                self.logger.info("Loaded plugin: %s", plugin.name)

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
