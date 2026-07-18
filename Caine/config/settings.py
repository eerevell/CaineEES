"""Typed YAML configuration for Caine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class MemorySettings:
    """Persistent memory settings."""

    data_dir: Path
    sqlite_file: str
    checkpoint_file: str

    @property
    def database_path(self) -> Path:
        """Return the SQLite database path."""

        return self.data_dir / self.sqlite_file

    @property
    def checkpoint_path(self) -> Path:
        """Return the checkpoint JSON path."""

        return self.data_dir / self.checkpoint_file


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    """Main loop runtime settings."""

    loop_interval_seconds: float
    checkpoint_interval_seconds: float
    max_consecutive_failures: int
    shutdown_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class ObserverSettings:
    """System observer settings."""

    internet_probe_host: str
    internet_probe_port: int
    internet_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class ReasoningSettings:
    """Local and remote model routing settings."""

    local_model_name: str
    remote_api_url: str
    remote_timeout_seconds: float
    complexity_threshold: int


@dataclass(frozen=True, slots=True)
class UpdateSettings:
    """Git based self-update settings."""

    repository_url: str
    branch: str
    current_dir: Path
    update_dir: Path
    symlink_path: Path
    check_interval_seconds: float
    requirements_file: str
    test_command: list[str]


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    """Logging settings."""

    level: str
    file_path: Path


@dataclass(frozen=True, slots=True)
class PluginSettings:
    """Plugin loading settings."""

    enabled: bool
    directories: list[Path] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Settings:
    """Top-level Caine settings."""

    memory: MemorySettings
    runtime: RuntimeSettings
    observer: ObserverSettings
    reasoning: ReasoningSettings
    update: UpdateSettings
    logging: LoggingSettings
    plugins: PluginSettings


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Configuration section '{name}' must be a mapping")
    return value


def load_settings(path: Path) -> Settings:
    """Load and validate settings from YAML."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    config = _require_mapping(raw, "root")
    memory = _require_mapping(config.get("memory"), "memory")
    runtime = _require_mapping(config.get("runtime"), "runtime")
    observer = _require_mapping(config.get("observer"), "observer")
    reasoning = _require_mapping(config.get("reasoning"), "reasoning")
    update = _require_mapping(config.get("update"), "update")
    logging = _require_mapping(config.get("logging"), "logging")
    plugins = _require_mapping(config.get("plugins"), "plugins")

    return Settings(
        memory=MemorySettings(
            data_dir=Path(memory["data_dir"]),
            sqlite_file=str(memory["sqlite_file"]),
            checkpoint_file=str(memory["checkpoint_file"]),
        ),
        runtime=RuntimeSettings(
            loop_interval_seconds=float(runtime["loop_interval_seconds"]),
            checkpoint_interval_seconds=float(
                runtime["checkpoint_interval_seconds"],
            ),
            max_consecutive_failures=int(runtime["max_consecutive_failures"]),
            shutdown_timeout_seconds=float(
                runtime["shutdown_timeout_seconds"],
            ),
        ),
        observer=ObserverSettings(
            internet_probe_host=str(observer["internet_probe_host"]),
            internet_probe_port=int(observer["internet_probe_port"]),
            internet_timeout_seconds=float(
                observer["internet_timeout_seconds"],
            ),
        ),
        reasoning=ReasoningSettings(
            local_model_name=str(reasoning["local_model_name"]),
            remote_api_url=str(reasoning["remote_api_url"]),
            remote_timeout_seconds=float(reasoning["remote_timeout_seconds"]),
            complexity_threshold=int(reasoning["complexity_threshold"]),
        ),
        update=UpdateSettings(
            repository_url=str(update["repository_url"]),
            branch=str(update["branch"]),
            current_dir=Path(update["current_dir"]),
            update_dir=Path(update["update_dir"]),
            symlink_path=Path(update["symlink_path"]),
            check_interval_seconds=float(update["check_interval_seconds"]),
            requirements_file=str(update["requirements_file"]),
            test_command=[str(part) for part in update["test_command"]],
        ),
        logging=LoggingSettings(
            level=str(logging["level"]),
            file_path=Path(logging["file_path"]),
        ),
        plugins=PluginSettings(
            enabled=bool(plugins["enabled"]),
            directories=[
                Path(item) for item in plugins.get("directories", [])
            ],
        ),
    )
