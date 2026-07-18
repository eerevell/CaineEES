"""Tests for EventBus, HealthManager, and Watchdog."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from Caine.core.event_bus import EventBus
from Caine.core.health import HealthManager
from Caine.core.models import ComponentHealth, ComponentStatus
from Caine.core.watchdog import Watchdog
from Caine.tests.conftest import make_test_logger


@pytest.mark.asyncio
async def test_event_bus_dispatches_subscribers() -> None:
    bus = EventBus(make_test_logger())
    seen: list[str] = []

    async def handler(event) -> None:
        seen.append(event.payload["value"])

    bus.subscribe("sample", handler)
    await bus.publish("sample", {"value": "ok"}, source="test")

    count = await bus.drain()

    assert count == 1
    assert seen == ["ok"]


@pytest.mark.asyncio
async def test_health_manager_runs_recovery() -> None:
    recovered: list[str] = []
    manager = HealthManager(make_test_logger())

    async def check() -> ComponentHealth:
        return ComponentHealth(
            name="Network",
            status=ComponentStatus.UNHEALTHY,
            message="down",
        )

    async def recover() -> None:
        recovered.append("network")

    manager.register("Network", check, recover)

    health = await manager.check_all()

    assert health["Network"].status == ComponentStatus.UNHEALTHY
    assert recovered == ["network"]


@pytest.mark.asyncio
async def test_watchdog_restarts_stale_component() -> None:
    restarted: list[str] = []
    watchdog = Watchdog(1.0, make_test_logger())

    async def restart() -> None:
        restarted.append("brain")

    watchdog.register("brain", restart)
    watchdog.heartbeats["brain"] = datetime.now(UTC) - timedelta(seconds=2)

    result = await watchdog.check()

    assert result == ["brain"]
    assert restarted == ["brain"]
