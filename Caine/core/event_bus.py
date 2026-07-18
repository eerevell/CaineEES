"""Asynchronous in-process event bus."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable
from uuid import uuid4

EventHandler = Callable[["Event"], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Event:
    """A domain event exchanged by Caine modules."""

    name: str
    payload: dict[str, Any]
    source: str
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class EventBus:
    """Decouple modules through asynchronous events."""

    logger: logging.Logger
    _subscribers: dict[str, list[EventHandler]] = field(default_factory=dict)
    _queue: asyncio.Queue[Event] = field(default_factory=asyncio.Queue)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event name."""

        self._subscribers.setdefault(event_name, []).append(handler)

    async def publish(
        self,
        event_name: str,
        payload: dict[str, Any],
        source: str,
    ) -> None:
        """Publish an event into the bus."""

        await self._queue.put(Event(event_name, payload, source))

    async def drain(self) -> int:
        """Dispatch all queued events and return dispatch count."""

        count = 0
        while not self._queue.empty():
            event = await self._queue.get()
            handlers = [
                *self._subscribers.get(event.name, []),
                *self._subscribers.get("*", []),
            ]
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as exc:
                    self.logger.exception(
                        "Event handler failed for %s: %s",
                        event.name,
                        exc,
                    )
            count += 1
        return count

