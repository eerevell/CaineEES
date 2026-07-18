"""Top-level coordinator for the autonomous runtime."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from Caine.config.settings import Settings
from Caine.core.critic import Critic
from Caine.core.executor import Executor
from Caine.core.models import Goal, Task, TaskStatus
from Caine.core.observer import Observer
from Caine.core.planner import Planner
from Caine.core.reasoning import Reasoning
from Caine.core.scheduler import PeriodicJob, Scheduler
from Caine.core.shutdown import ShutdownManager
from Caine.core.updater import Updater
from Caine.memory.store import MemoryStore


@dataclass(slots=True)
class Brain:
    """Coordinate Caine modules without owning business logic."""

    settings: Settings
    memory: MemoryStore
    planner: Planner
    observer: Observer
    executor: Executor
    critic: Critic
    reasoning: Reasoning
    scheduler: Scheduler
    updater: Updater
    shutdown: ShutdownManager
    logger: logging.Logger
    current_goal: Goal | None = None
    accepting_new_tasks: bool = True

    async def initialize(self, goal: Goal | None, queue: list[Task]) -> None:
        """Restore runtime state and register periodic jobs."""

        self.current_goal = goal
        await self.planner.restore(queue)
        self.scheduler.add_job(
            PeriodicJob(
                name="checkpoint",
                interval_seconds=(
                    self.settings.runtime.checkpoint_interval_seconds
                ),
                action=self.save_checkpoint,
            ),
        )
        self.scheduler.add_job(
            PeriodicJob(
                name="updater",
                interval_seconds=self.settings.update.check_interval_seconds,
                action=self._safe_update,
            ),
        )
        self.shutdown.register(self._shutdown)

    async def run_forever(self) -> None:
        """Run the main autonomous loop until shutdown is requested."""

        self.shutdown.install_signal_handlers()
        while not self.shutdown.requested:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.exception("Brain loop failed: %s", exc)
                await self.memory.remember(
                    "errors",
                    datetime.now(UTC).isoformat(),
                    {"source": "brain", "message": str(exc)},
                )
            await asyncio.sleep(self.settings.runtime.loop_interval_seconds)
        await self.shutdown.cleanup()

    async def run_once(self) -> None:
        """Execute one full autonomous cycle."""

        state = await self.observer.observe()
        state_data = asdict(state)
        await self.memory.remember("system", "last_state", state_data)
        pending_tasks = self.planner.pending_count()
        decision = await self.reasoning.decide(
            "Determine the next autonomous action",
            {
                "system": state_data,
                "pending_tasks": pending_tasks,
                "current_goal": self.current_goal.description
                if self.current_goal
                else None,
            },
        )
        self.logger.debug("Reasoning decision: %s", decision)

        if self.accepting_new_tasks and not self.critic.should_pause():
            self.current_goal = await self.planner.plan(state)
            await self.memory.save_goal(self.current_goal)
            await self.planner.ensure_tasks_for_goal(self.current_goal)

        task = await self.planner.next_task()
        if task is not None:
            result = await self.executor.execute(task)
            accepted = self.critic.evaluate(task, result)
            await self.memory.record_experience(
                task.id,
                result.success,
                result.message,
                result.data,
            )
            if accepted:
                task.status = TaskStatus.SUCCEEDED
                await self.memory.save_task(task)
            else:
                await self.planner.requeue_or_fail(task)

        await self.scheduler.tick()

    async def save_checkpoint(self) -> None:
        """Save a recoverable runtime checkpoint."""

        await self.memory.persist_checkpoint(
            self.settings.memory.checkpoint_path,
            self.current_goal,
            self.planner.snapshot(),
        )
        self.logger.debug("Checkpoint saved")

    async def _safe_update(self) -> None:
        try:
            await self.updater.check_and_update()
        except Exception as exc:
            self.logger.exception(
                "Update failed and current version remains: %s",
                exc,
            )

    async def _shutdown(self, reason: str) -> None:
        self.accepting_new_tasks = False
        await self.memory.remember(
            "runtime",
            "last_shutdown",
            {"reason": reason, "requested_at": datetime.now(UTC).isoformat()},
        )
        await self.save_checkpoint()
        await self.memory.close()
