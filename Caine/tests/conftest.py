"""Shared test fixtures."""

from __future__ import annotations

import logging
from pathlib import Path

from Caine.config.settings import (
    LoggingSettings,
    MemorySettings,
    NetworkSettings,
    ObserverSettings,
    PluginSettings,
    ReasoningSettings,
    RuntimeSettings,
    Settings,
    UpdateSettings,
)


def make_settings(tmp_path: Path) -> Settings:
    """Build isolated settings for tests."""

    return Settings(
        memory=MemorySettings(
            data_dir=tmp_path / "data",
            sqlite_file="caine.sqlite3",
            checkpoint_file="checkpoint.json",
        ),
        runtime=RuntimeSettings(
            loop_interval_seconds=0.01,
            checkpoint_interval_seconds=0.01,
            max_consecutive_failures=2,
            shutdown_timeout_seconds=1.0,
            watchdog_timeout_seconds=5.0,
        ),
        observer=ObserverSettings(
            internet_probe_host="127.0.0.1",
            internet_probe_port=9,
            internet_timeout_seconds=0.01,
            systemd_services=[],
        ),
        reasoning=ReasoningSettings(
            local_model_name="test-local",
            remote_api_url="http://example.invalid/reason",
            remote_timeout_seconds=0.01,
            complexity_threshold=3,
        ),
        network=NetworkSettings(
            remote_node_name="EES2",
            heartbeat_url="http://127.0.0.1:1/health",
            heartbeat_interval_seconds=999.0,
            reconnect_backoff_seconds=0.01,
            max_reconnect_backoff_seconds=0.01,
        ),
        update=UpdateSettings(
            repository_url="git@example.com:test/caine.git",
            branch="main",
            current_dir=tmp_path / "current",
            update_dir=tmp_path / "update",
            symlink_path=tmp_path / "caine",
            check_interval_seconds=999.0,
            requirements_file="requirements.txt",
            test_command=["python", "-m", "pytest"],
            startup_probe_command=["python", "-m", "pytest"],
            metadata_file=str(tmp_path / "data" / "version.json"),
        ),
        logging=LoggingSettings(
            level="DEBUG",
            file_path=tmp_path / "logs" / "caine.log",
        ),
        plugins=PluginSettings(enabled=True, directories=[]),
    )


def make_test_logger() -> logging.Logger:
    """Return a quiet test logger."""

    logger = logging.getLogger("caine.tests")
    logger.addHandler(logging.NullHandler())
    return logger
