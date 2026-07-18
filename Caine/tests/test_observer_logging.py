"""Tests for observer and logging setup."""

from __future__ import annotations

import pytest

from Caine.config.settings import LoggingSettings
from Caine.core.logging_setup import configure_logging
from Caine.core.observer import Observer


@pytest.mark.asyncio
async def test_observer_returns_system_state(monkeypatch) -> None:
    async def internet_available(self) -> bool:
        return True

    monkeypatch.setattr(Observer, "_internet_available", internet_available)
    observer = Observer("127.0.0.1", 9, 0.01)

    state = await observer.observe()

    assert state.internet_available is True
    assert state.cpu_percent >= 0
    assert state.ram_percent >= 0
    assert state.disk_percent >= 0


def test_configure_logging_creates_log_file(tmp_path) -> None:
    log_path = tmp_path / "logs" / "caine.log"
    logger = configure_logging(
        LoggingSettings(level="INFO", file_path=log_path),
    )

    logger.info("hello")

    assert log_path.exists()
