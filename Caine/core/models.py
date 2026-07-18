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


@dataclass(slots=True)
class Checkpoint:
    """Recoverable runtime state."""

    current_goal: Goal | None
    task_queue: list[Task]
    saved_at: datetime = field(default_factory=lambda: datetime.now(UTC))

