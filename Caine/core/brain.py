"""Top-level coordinator for the autonomous runtime."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from Caine.config.settings import Settings
from Caine.core.critic import Critic
from Caine.core.event_bus import EventBus
from Caine.core.executor import Executor
from Caine.core.health import HealthManager
from Caine.core.models import Goal, Task
from Caine.core.observer import Observer
from Caine.core.planner import Planner
from Caine.core.reasoning import Reasoning
from Caine.core.scheduler import PeriodicJob, Scheduler
from Caine.core.shutdown import ShutdownManager
from Caine.core.updater import Updater
from Caine.core.watchdog import Watchdog
from Caine.memory.store import MemoryStore
from Caine.network.compute_node import ComputeNodeClient
from Caine.plugins.registry import PluginRegistry


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
    event_bus: EventBus
    health: HealthManager
    watchdog: Watchdog
    compute_node: ComputeNodeClient
    logger: logging.Logger
    plugins: PluginRegistry | None = None
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
        self.scheduler.add_job(
            PeriodicJob(
                name="remote_node_heartbeat",
                interval_seconds=(
                    self.settings.network.heartbeat_interval_seconds
                ),
                action=self._heartbeat_remote_node,
            ),
        )
        self.scheduler.add_job(
            PeriodicJob(
                name="health",
                interval_seconds=self.settings.runtime.loop_interval_seconds,
                action=self._check_health,
            ),
        )
        self.scheduler.add_job(
            PeriodicJob(
                name="watchdog",
                interval_seconds=self.settings.runtime.loop_interval_seconds,
                action=self._check_watchdog,
            ),
        )
        self.shutdown.register(self._shutdown)
        self._register_health_checks()

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
        self.watchdog.beat("brain")
        await self.event_bus.publish(
            "brain.cycle.started",
            {"state": state_data},
            source="brain",
        )
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
        await self.event_bus.publish(
            "brain.decision.made",
            {"decision": decision},
            source="brain",
        )

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
                await self.planner.complete_successfully(task)
            else:
                await self.planner.requeue_or_fail(task)
            await self.event_bus.publish(
                "task.finished",
                {
                    "task_id": task.id,
                    "success": result.success,
                    "message": result.message,
                },
                source="brain",
            )

        if self.plugins is not None:
            await self.plugins.tick()
        await self.scheduler.tick()
        await self.event_bus.drain()

    async def save_checkpoint(self) -> None:
        """Save a recoverable runtime checkpoint."""

        await self.memory.persist_checkpoint(
            self.settings.memory.checkpoint_path,
            self.current_goal,
            self.planner.snapshot(),
            planner_state=self.planner.planner_state(),
            memory_state={"repository": "sqlite"},
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
        await self.event_bus.publish(
            "brain.shutdown.requested",
            {"reason": reason},
            source="brain",
        )
        started = asyncio.get_running_loop().time()
        while self.executor.has_active_tasks():
            elapsed = asyncio.get_running_loop().time() - started
            if elapsed >= self.settings.runtime.shutdown_timeout_seconds:
                self.logger.warning("Shutdown timed out waiting for tasks")
                break
            await asyncio.sleep(0.1)
        if self.plugins is not None:
            await self.plugins.stop()
        await self.memory.remember(
            "runtime",
            "last_shutdown",
            {"reason": reason, "requested_at": datetime.now(UTC).isoformat()},
        )
        await self.save_checkpoint()
        await self.compute_node.close()
        await self.memory.remember(
            "runtime",
            "last_shutdown_confirmed",
            {"confirmed_at": datetime.now(UTC).isoformat()},
        )
        await self.memory.close()

    async def _heartbeat_remote_node(self) -> None:
        state = await self.compute_node.heartbeat()
        self.observer.remote_node_state = state
        await self.memory.remember(
            "network",
            "remote_node",
            {
                "name": state.name,
                "available": state.available,
                "failure_count": state.failure_count,
                "message": state.message,
                "last_seen_at": state.last_seen_at.isoformat()
                if state.last_seen_at
                else None,
            },
        )

    async def _check_health(self) -> None:
        health = await self.health.check_all()
        await self.memory.remember(
            "health",
            "latest",
            {
                name: {
                    "status": item.status.value,
                    "message": item.message,
                    "checked_at": item.checked_at.isoformat(),
                }
                for name, item in health.items()
            },
        )

    async def _check_watchdog(self) -> None:
        restarted = await self.watchdog.check()
        if restarted:
            await self.event_bus.publish(
                "watchdog.restarted",
                {"components": restarted},
                source="watchdog",
            )

    def _register_health_checks(self) -> None:
        from Caine.core.models import ComponentHealth, ComponentStatus

        async def healthy(name: str) -> ComponentHealth:
            return ComponentHealth(
                name=name,
                status=ComponentStatus.HEALTHY,
                message="ok",
            )

        async def remote_node() -> ComponentHealth:
            return ComponentHealth(
                name="Remote Node",
                status=ComponentStatus.HEALTHY
                if self.compute_node.state.available
                else ComponentStatus.DEGRADED,
                message=self.compute_node.state.message,
            )

        for name in (
            "Brain",
            "Memory",
            "SQLite",
            "Updater",
            "Scheduler",
        ):
            self.health.register(name, lambda n=name: healthy(n))
        self.health.register("Remote Node", remote_node)
        self.watchdog.register("brain", self.save_checkpoint)
