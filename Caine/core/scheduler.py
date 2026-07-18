"""Async scheduler for periodic runtime activities."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

ScheduledAction = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class PeriodicJob:
    """A periodic async job."""

    name: str
    interval_seconds: float
    action: ScheduledAction
    last_run: float = field(default_factory=time.monotonic)

    async def run_if_due(self, now: float) -> bool:
        """Run the action when enough time has elapsed."""

        if now - self.last_run < self.interval_seconds:
            return False
        await self.action()
        self.last_run = now
        return True


@dataclass(slots=True)
class Scheduler:
    """Cooperative periodic scheduler."""

    jobs: list[PeriodicJob] = field(default_factory=list)

    def add_job(self, job: PeriodicJob) -> None:
        """Register a periodic job."""

        self.jobs.append(job)

    async def tick(self) -> list[str]:
        """Run all due jobs and return executed names."""

        now = time.monotonic()
        executed: list[str] = []
        for job in self.jobs:
            if await job.run_if_due(now):
                executed.append(job.name)
        return executed
