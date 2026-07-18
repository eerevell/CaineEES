"""Shared domain models for the Caine runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class TaskStatus(str, Enum):
    """Known task lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrganismState(str, Enum):
    """High-level EES1 organism states."""

    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    UPDATING = "updating"
    SHUTTING_DOWN = "shutting_down"


class ComponentStatus(str, Enum):
    """Component health states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"


@dataclass(slots=True)
class Task:
    """A single autonomous work item."""

    kind: str
    payload: dict[str, Any]
    priority: int = 100
    id: str = field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    dependencies: list[str] = field(default_factory=list)
    not_before: datetime | None = None
    deadline: datetime | None = None
    repeat_interval_seconds: float | None = None
    cancelled_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Goal:
    """A high-level objective selected by the brain."""

    description: str
    priority: int = 100
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ExecutionResult:
    """Result returned by an executor."""

    task_id: str
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SystemState:
    """Observed system health snapshot."""

    cpu_percent: float
    ram_percent: float
    disk_percent: float
    temperature_celsius: float | None
    internet_available: bool
    modules: dict[str, bool]
    disk_temperatures: dict[str, float] = field(default_factory=dict)
    smart_health: dict[str, str] = field(default_factory=dict)
    battery_percent: float | None = None
    battery_power_plugged: bool | None = None
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    systemd_services: dict[str, bool] = field(default_factory=dict)
    remote_node_available: bool = False


@dataclass(slots=True)
class Checkpoint:
    """Recoverable runtime state."""

    current_goal: Goal | None
    task_queue: list[Task]
    planner_state: dict[str, Any] = field(default_factory=dict)
    memory_state: dict[str, Any] = field(default_factory=dict)
    saved_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ComponentHealth:
    """Health information for a single component."""

    name: str
    status: ComponentStatus
    message: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class RemoteNodeState:
    """State of the EES2 compute node."""

    name: str
    available: bool
    last_seen_at: datetime | None = None
    failure_count: int = 0
    message: str = ""
