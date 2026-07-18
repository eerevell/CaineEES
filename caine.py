"""Executable entry point for Caine."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from Caine.config.settings import load_settings
from Caine.core.brain import Brain
from Caine.core.critic import Critic
from Caine.core.executor import Executor, system_check_handler
from Caine.core.logging_setup import configure_logging
from Caine.core.observer import Observer
from Caine.core.planner import Planner
from Caine.core.reasoning import Reasoning
from Caine.core.scheduler import Scheduler
from Caine.core.shutdown import ShutdownManager
from Caine.core.startup import StartupManager
from Caine.core.updater import AsyncCommandRunner, Updater
from Caine.memory.store import MemoryStore
from Caine.network.remote_reasoning import RemoteReasoningClient
from Caine.plugins.registry import PluginRegistry


async def main() -> None:
    """Build dependencies and run Caine."""

    parser = argparse.ArgumentParser(description="Caine autonomous runtime")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("Caine/config/caine.yaml"),
        help="Path to YAML configuration",
    )
    args = parser.parse_args()

    settings = load_settings(args.config)
    logger = configure_logging(settings.logging)
    memory = MemoryStore(settings.memory.database_path)
    startup = StartupManager(settings=settings, memory=memory, logger=logger)
    restored_goal, restored_queue = await startup.initialize()

    executor = Executor(
        logger=logger.getChild("executor"),
        handlers={"system_check": system_check_handler},
    )
    if settings.plugins.enabled:
        registry = PluginRegistry(
            directories=settings.plugins.directories,
            logger=logger.getChild("plugins"),
        )
        await registry.load(executor)

    remote_client = RemoteReasoningClient(
        api_url=settings.reasoning.remote_api_url,
        timeout_seconds=settings.reasoning.remote_timeout_seconds,
        logger=logger.getChild("remote_reasoning"),
    )
    brain = Brain(
        settings=settings,
        memory=memory,
        planner=Planner(memory=memory, logger=logger.getChild("planner")),
        observer=Observer(
            internet_probe_host=settings.observer.internet_probe_host,
            internet_probe_port=settings.observer.internet_probe_port,
            internet_timeout_seconds=(
                settings.observer.internet_timeout_seconds
            ),
        ),
        executor=executor,
        critic=Critic(
            max_consecutive_failures=(
                settings.runtime.max_consecutive_failures
            ),
            logger=logger.getChild("critic"),
        ),
        reasoning=Reasoning(
            settings=settings.reasoning,
            remote_client=remote_client,
            logger=logger.getChild("reasoning"),
        ),
        scheduler=Scheduler(),
        updater=Updater(
            settings=settings.update,
            logger=logger.getChild("updater"),
            runner=AsyncCommandRunner(),
        ),
        shutdown=ShutdownManager(logger=logger.getChild("shutdown")),
        logger=logger.getChild("brain"),
    )
    await brain.initialize(restored_goal, restored_queue)
    await brain.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
