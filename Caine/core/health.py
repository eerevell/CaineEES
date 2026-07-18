"""Health manager for runtime components."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from Caine.core.models import ComponentHealth, ComponentStatus

HealthCheck = Callable[[], Awaitable[ComponentHealth]]
RecoveryAction = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class HealthManager:
    """Monitor components and attempt local recovery."""

    logger: logging.Logger
    checks: dict[str, HealthCheck] = field(default_factory=dict)
    recoveries: dict[str, RecoveryAction] = field(default_factory=dict)
    latest: dict[str, ComponentHealth] = field(default_factory=dict)

    def register(
        self,
        name: str,
        check: HealthCheck,
        recovery: RecoveryAction | None = None,
    ) -> None:
        """Register a component health check and optional recovery."""

        self.checks[name] = check
        if recovery is not None:
            self.recoveries[name] = recovery

    async def check_all(self) -> dict[str, ComponentHealth]:
        """Check every registered component."""

        for name, check in self.checks.items():
            try:
                health = await check()
            except Exception as exc:
                health = ComponentHealth(
                    name=name,
                    status=ComponentStatus.UNHEALTHY,
                    message=str(exc),
                )
            self.latest[name] = health
            if health.status == ComponentStatus.UNHEALTHY:
                await self._recover(name)
        return dict(self.latest)

    async def _recover(self, name: str) -> None:
        recovery = self.recoveries.get(name)
        if recovery is None:
            return
        self.logger.warning("Attempting recovery for component %s", name)
        try:
            await recovery()
        except Exception as exc:
            self.logger.exception("Recovery failed for %s: %s", name, exc)

    def component_flags(self) -> dict[str, bool]:
        """Return simplified component health flags."""

        return {
            name: health.status == ComponentStatus.HEALTHY
            for name, health in self.latest.items()
        }

