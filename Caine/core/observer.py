"""System observer for Debian hosts."""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass

import psutil

from Caine.core.models import RemoteNodeState, SystemState


@dataclass(slots=True)
class Observer:
    """Collect system and module health."""

    internet_probe_host: str
    internet_probe_port: int
    internet_timeout_seconds: float
    systemd_services: list[str] | None = None
    remote_node_state: RemoteNodeState | None = None

    async def observe(self) -> SystemState:
        """Return a fresh system state snapshot."""

        return SystemState(
            cpu_percent=float(psutil.cpu_percent(interval=None)),
            ram_percent=float(psutil.virtual_memory().percent),
            disk_percent=self._disk_percent(),
            temperature_celsius=self._temperature(),
            internet_available=await self._internet_available(),
            modules={},
            disk_temperatures=self._disk_temperatures(),
            smart_health=await self._smart_health(),
            battery_percent=self._battery_percent(),
            battery_power_plugged=self._battery_power_plugged(),
            network_bytes_sent=self._network_bytes_sent(),
            network_bytes_recv=self._network_bytes_recv(),
            systemd_services=await self._systemd_services(),
            remote_node_available=(
                self.remote_node_state.available
                if self.remote_node_state
                else False
            ),
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

    def _disk_temperatures(self) -> dict[str, float]:
        try:
            sensors = psutil.sensors_temperatures()
        except (AttributeError, OSError):
            return {}
        return {
            name: max(item.current for item in entries)
            for name, entries in sensors.items()
            if entries and all(item.current is not None for item in entries)
        }

    async def _smart_health(self) -> dict[str, str]:
        devices = [partition.device for partition in psutil.disk_partitions()]
        health: dict[str, str] = {}
        for device in devices:
            health[device] = await self._smart_status(device)
        return health

    async def _smart_status(self, device: str) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                "smartctl",
                "-H",
                device,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=2,
            )
        except (OSError, TimeoutError):
            return "unknown"
        output = stdout.decode(errors="replace").lower()
        if "passed" in output:
            return "passed"
        if "failed" in output:
            return "failed"
        return "unknown"

    def _battery_percent(self) -> float | None:
        battery = psutil.sensors_battery()
        return float(battery.percent) if battery is not None else None

    def _battery_power_plugged(self) -> bool | None:
        battery = psutil.sensors_battery()
        return bool(battery.power_plugged) if battery is not None else None

    def _network_bytes_sent(self) -> int:
        return int(psutil.net_io_counters().bytes_sent)

    def _network_bytes_recv(self) -> int:
        return int(psutil.net_io_counters().bytes_recv)

    async def _systemd_services(self) -> dict[str, bool]:
        services = self.systemd_services or []
        states: dict[str, bool] = {}
        for service in services:
            states[service] = await self._systemd_service_active(service)
        return states

    async def _systemd_service_active(self, service: str) -> bool:
        try:
            process = await asyncio.create_subprocess_exec(
                "systemctl",
                "is-active",
                "--quiet",
                service,
            )
            await asyncio.wait_for(process.wait(), timeout=2)
            return process.returncode == 0
        except (OSError, TimeoutError):
            return False

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
