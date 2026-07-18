"""Internal watchdog for component responsiveness."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Awaitable, Callable

RestartAction = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class Watchdog:
    """Detect stale components and restart only the affected component."""

    timeout_seconds: float
    logger: logging.Logger
    restarts: dict[str, RestartAction] = field(default_factory=dict)
    heartbeats: dict[str, datetime] = field(default_factory=dict)

    def register(self, component: str, restart: RestartAction) -> None:
        """Register restart action for a component."""

        self.restarts[component] = restart
        self.beat(component)

    def beat(self, component: str) -> None:
        """Mark a component as responsive."""

        self.heartbeats[component] = datetime.now(UTC)

    async def check(self) -> list[str]:
        """Restart stale components and return their names."""

        restarted: list[str] = []
        now = datetime.now(UTC)
        for component, last_seen in list(self.heartbeats.items()):
            age = (now - last_seen).total_seconds()
            if age <= self.timeout_seconds:
                continue
            restart = self.restarts.get(component)
            if restart is None:
                continue
            self.logger.warning("Watchdog restarting %s", component)
            await restart()
            self.beat(component)
            restarted.append(component)
        return restarted
