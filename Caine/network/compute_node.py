"""Async EES2 compute-node client."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import aiohttp

from Caine.config.settings import NetworkSettings, ReasoningSettings
from Caine.core.event_bus import EventBus
from Caine.core.models import RemoteNodeState


@dataclass(slots=True)
class ComputeNodeClient:
    """HTTP client for EES2 as a compute-only coprocessor."""

    network_settings: NetworkSettings
    reasoning_settings: ReasoningSettings
    logger: logging.Logger
    event_bus: EventBus | None = None
    state: RemoteNodeState = field(init=False)
    _session: aiohttp.ClientSession | None = field(default=None, init=False)
    _backoff_seconds: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.state = RemoteNodeState(
            name=self.network_settings.remote_node_name,
            available=False,
            message="not checked",
        )
        self._backoff_seconds = self.network_settings.reconnect_backoff_seconds

    async def open(self) -> None:
        """Open HTTP resources."""

        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=self.reasoning_settings.remote_timeout_seconds,
            )
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        """Close HTTP resources."""

        if self._session is not None:
            await self._session.close()
            self._session = None

    async def heartbeat(self) -> RemoteNodeState:
        """Check EES2 availability and publish state changes."""

        await self.open()
        previous = self.state.available
        try:
            assert self._session is not None
            async with self._session.get(
                self.network_settings.heartbeat_url,
            ) as response:
                if response.status >= 400:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message="heartbeat failed",
                    )
            self.state.available = True
            self.state.last_seen_at = datetime.now(UTC)
            self.state.failure_count = 0
            self.state.message = "available"
            self._backoff_seconds = (
                self.network_settings.reconnect_backoff_seconds
            )
        except (aiohttp.ClientError, TimeoutError, AssertionError) as exc:
            self.state.available = False
            self.state.failure_count += 1
            self.state.message = str(exc)
            await self._reconnect_after_backoff()

        if previous != self.state.available and self.event_bus is not None:
            await self.event_bus.publish(
                "network.remote_node.changed",
                {
                    "name": self.state.name,
                    "available": self.state.available,
                    "message": self.state.message,
                },
                source="network",
            )
        return self.state

    async def reason(self, prompt: str, context: dict[str, Any]) -> str | None:
        """Send an inference request to EES2 when available."""

        if not self.state.available:
            return None
        await self.open()
        try:
            assert self._session is not None
            async with self._session.post(
                self.reasoning_settings.remote_api_url,
                json={"prompt": prompt, "context": context},
            ) as response:
                if response.status >= 400:
                    self.logger.warning(
                        "EES2 inference failed with HTTP %s",
                        response.status,
                    )
                    return None
                payload = await response.json()
                answer = payload.get("answer")
                return str(answer) if answer is not None else None
        except (aiohttp.ClientError, TimeoutError, AssertionError) as exc:
            self.logger.warning("EES2 inference unavailable: %s", exc)
            self.state.available = False
            return None

    async def _reconnect_after_backoff(self) -> None:
        await self.close()
        await asyncio.sleep(min(self._backoff_seconds, 0.1))
        self._backoff_seconds = min(
            self._backoff_seconds * 2,
            self.network_settings.max_reconnect_backoff_seconds,
        )
