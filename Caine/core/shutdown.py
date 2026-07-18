"""Graceful shutdown handling."""

from __future__ import annotations

import asyncio
import logging
import signal
from dataclasses import dataclass, field
from typing import Awaitable, Callable

ShutdownCallback = Callable[[str], Awaitable[None]]


@dataclass(slots=True)
class ShutdownManager:
    """Coordinate SIGTERM/SIGINT shutdown and cleanup."""

    logger: logging.Logger
    _callbacks: list[ShutdownCallback] = field(default_factory=list)
    _reason: str | None = None
    _event: asyncio.Event = field(default_factory=asyncio.Event)

    def install_signal_handlers(self) -> None:
        """Install Unix signal handlers for graceful shutdown."""

        loop = asyncio.get_running_loop()
        for signum in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(
                    signum,
                    self.request_shutdown,
                    signal.Signals(signum).name,
                )
            except NotImplementedError:
                signal.signal(
                    signum,
                    lambda received, _frame: self.request_shutdown(
                        signal.Signals(received).name,
                    ),
                )

    def register(self, callback: ShutdownCallback) -> None:
        """Register an async cleanup callback."""

        self._callbacks.append(callback)

    def request_shutdown(self, reason: str) -> None:
        """Request graceful shutdown."""

        if self._reason is None:
            self._reason = reason
            self.logger.info("Shutdown requested: %s", reason)
            self._event.set()

    async def wait(self) -> str:
        """Wait until shutdown is requested and return the reason."""

        await self._event.wait()
        return self._reason or "unknown"

    async def cleanup(self) -> None:
        """Run registered cleanup callbacks in reverse order."""

        reason = self._reason or "unknown"
        for callback in reversed(self._callbacks):
            await callback(reason)

    @property
    def requested(self) -> bool:
        """Return whether shutdown has been requested."""

        return self._event.is_set()

