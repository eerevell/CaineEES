"""System observer for Debian hosts."""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass

import psutil

from Caine.core.models import SystemState


@dataclass(slots=True)
class Observer:
    """Collect system and module health."""

    internet_probe_host: str
    internet_probe_port: int
    internet_timeout_seconds: float

    async def observe(self) -> SystemState:
        """Return a fresh system state snapshot."""

        return SystemState(
            cpu_percent=float(psutil.cpu_percent(interval=None)),
            ram_percent=float(psutil.virtual_memory().percent),
            disk_percent=self._disk_percent(),
            temperature_celsius=self._temperature(),
            internet_available=await self._internet_available(),
            modules={},
        )

    def _disk_percent(self) -> float:
        usage = shutil.disk_usage("/")
        return (usage.used / usage.total) * 100

    def _temperature(self) -> float | None:
        try:
            sensors = psutil.sensors_temperatures()
        except (AttributeError, OSError):
            return None
        values = [
            item.current
            for entries in sensors.values()
            for item in entries
            if item.current is not None
        ]
        return max(values) if values else None

    async def _internet_available(self) -> bool:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.internet_probe_host,
                    self.internet_probe_port,
                ),
                timeout=self.internet_timeout_seconds,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except OSError:
            return False
        except TimeoutError:
            return False

