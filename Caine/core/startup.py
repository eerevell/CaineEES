"""Startup and crash recovery orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from Caine.config.settings import Settings
from Caine.core.models import Goal, Task
from Caine.memory.store import MemoryStore


@dataclass(slots=True)
class StartupManager:
    """Prepare durable runtime dependencies and recover checkpoints."""

    settings: Settings
    memory: MemoryStore
    logger: logging.Logger

    async def initialize(self) -> tuple[Goal | None, list[Task]]:
        """Open memory and restore checkpoint state."""

        await self.memory.open()
        goal, queue, metadata = await self.memory.load_checkpoint(
            self.settings.memory.checkpoint_path,
        )
        if goal or queue:
            self.logger.info(
                "Recovered checkpoint with goal=%s tasks=%s saved_at=%s",
                goal.id if goal else None,
                len(queue),
                metadata.get("saved_at"),
            )
        return goal, queue
