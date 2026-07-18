"""SQLite-backed persistent memory."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from Caine.core.models import Goal, Task, TaskStatus


class MemoryStore:
    """Durable memory storage backed by SQLite."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._connection: sqlite3.Connection | None = None

    async def open(self) -> None:
        """Open the database and initialize the schema."""

        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await asyncio.to_thread(
            sqlite3.connect,
            self._database_path,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        await self._execute_script(SCHEMA_SQL)

    async def close(self) -> None:
        """Close the database connection."""

        if self._connection is None:
            return
        await asyncio.to_thread(self._connection.close)
        self._connection = None

    async def save_task(self, task: Task) -> None:
        """Insert or update a task."""

        query = """
            INSERT INTO tasks (
                id, kind, payload, priority, status, attempts, max_attempts,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload = excluded.payload,
                priority = excluded.priority,
                status = excluded.status,
                attempts = excluded.attempts,
                max_attempts = excluded.max_attempts,
                updated_at = excluded.updated_at
        """
        await self._execute(
            query,
            (
                task.id,
                task.kind,
                json.dumps(task.payload),
                task.priority,
                task.status.value,
                task.attempts,
                task.max_attempts,
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
            ),
        )

    async def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """List tasks, optionally filtered by status."""

        if status is None:
            rows = await self._fetch_all(
                "SELECT * FROM tasks ORDER BY priority ASC, created_at ASC",
                (),
            )
        else:
            rows = await self._fetch_all(
                """
                SELECT * FROM tasks
                WHERE status = ?
                ORDER BY priority ASC, created_at ASC
                """,
                (status.value,),
            )
        return [self._row_to_task(row) for row in rows]

    async def save_goal(self, goal: Goal) -> None:
        """Persist a goal."""

        await self._execute(
            """
            INSERT INTO goals (id, description, priority, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                description = excluded.description,
                priority = excluded.priority
            """,
            (
                goal.id,
                goal.description,
                goal.priority,
                goal.created_at.isoformat(),
            ),
        )

    async def remember(
        self,
        category: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Store arbitrary structured memory."""

        now = datetime.now(UTC).isoformat()
        await self._execute(
            """
            INSERT INTO memories (category, key, value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(category, key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (category, key, json.dumps(value), now, now),
        )

    async def recall(self, category: str, key: str) -> dict[str, Any] | None:
        """Load structured memory by category and key."""

        rows = await self._fetch_all(
            "SELECT value FROM memories WHERE category = ? AND key = ?",
            (category, key),
        )
        if not rows:
            return None
        return dict(json.loads(rows[0]["value"]))

    async def record_experience(
        self,
        task_id: str,
        success: bool,
        message: str,
        data: dict[str, Any],
    ) -> None:
        """Append execution experience."""

        await self._execute(
            """
            INSERT INTO experiences (
                task_id, success, message, data, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                task_id,
                int(success),
                message,
                json.dumps(data),
                datetime.now(UTC).isoformat(),
            ),
        )

    async def persist_checkpoint(
        self,
        path: Path,
        current_goal: Goal | None,
        queue: list[Task],
        planner_state: dict[str, Any] | None = None,
        memory_state: dict[str, Any] | None = None,
    ) -> None:
        """Persist a crash-recovery checkpoint outside the source tree."""

        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_goal": self._goal_to_json(current_goal),
            "task_queue": [self._task_to_json(task) for task in queue],
            "planner_state": planner_state or {},
            "memory_state": memory_state or {},
            "saved_at": datetime.now(UTC).isoformat(),
        }
        await asyncio.to_thread(path.write_text, json.dumps(payload), "utf-8")
        await self.remember("runtime", "last_checkpoint", payload)

    async def load_checkpoint(
        self,
        path: Path,
    ) -> tuple[Goal | None, list[Task], dict[str, Any]]:
        """Load the latest checkpoint if present."""

        if not path.exists():
            return None, [], {}
        raw = await asyncio.to_thread(path.read_text, "utf-8")
        payload = json.loads(raw)
        goal = self._dict_to_goal(payload["current_goal"])
        tasks = [self._dict_to_task(item) for item in payload["task_queue"]]
        metadata = {
            "planner_state": payload.get("planner_state", {}),
            "memory_state": payload.get("memory_state", {}),
            "saved_at": payload.get("saved_at"),
        }
        return goal, tasks, metadata

    async def _execute(self, query: str, parameters: tuple[Any, ...]) -> None:
        connection = self._require_connection()

        def run() -> None:
            connection.execute(query, parameters)
            connection.commit()

        await asyncio.to_thread(run)

    async def _execute_script(self, script: str) -> None:
        connection = self._require_connection()

        def run() -> None:
            connection.executescript(script)
            connection.commit()

        await asyncio.to_thread(run)

    async def _fetch_all(
        self,
        query: str,
        parameters: tuple[Any, ...],
    ) -> list[sqlite3.Row]:
        connection = self._require_connection()

        def run() -> list[sqlite3.Row]:
            cursor = connection.execute(query, parameters)
            return list(cursor.fetchall())

        return await asyncio.to_thread(run)

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("MemoryStore is not open")
        return self._connection

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            kind=row["kind"],
            payload=dict(json.loads(row["payload"])),
            priority=row["priority"],
            status=TaskStatus(row["status"]),
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _task_to_json(task: Task) -> dict[str, Any]:
        data = asdict(task)
        data["status"] = task.status.value
        data["created_at"] = task.created_at.isoformat()
        data["updated_at"] = task.updated_at.isoformat()
        if task.not_before is not None:
            data["not_before"] = task.not_before.isoformat()
        if task.deadline is not None:
            data["deadline"] = task.deadline.isoformat()
        return data

    @classmethod
    def _dict_to_task(cls, data: dict[str, Any]) -> Task:
        return Task(
            id=data["id"],
            kind=data["kind"],
            payload=dict(data["payload"]),
            priority=int(data["priority"]),
            status=TaskStatus(data["status"]),
            attempts=int(data["attempts"]),
            max_attempts=int(data["max_attempts"]),
            dependencies=list(data.get("dependencies", [])),
            not_before=cls._optional_datetime(data.get("not_before")),
            deadline=cls._optional_datetime(data.get("deadline")),
            repeat_interval_seconds=data.get("repeat_interval_seconds"),
            cancelled_reason=data.get("cancelled_reason"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    @staticmethod
    def _optional_datetime(value: str | None) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value)

    @staticmethod
    def _goal_to_json(goal: Goal | None) -> dict[str, Any] | None:
        if goal is None:
            return None
        return {
            "id": goal.id,
            "description": goal.description,
            "priority": goal.priority,
            "created_at": goal.created_at.isoformat(),
        }

    @staticmethod
    def _dict_to_goal(data: dict[str, Any] | None) -> Goal | None:
        if data is None:
            return None
        return Goal(
            id=data["id"],
            description=data["description"],
            priority=int(data["priority"]),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    priority INTEGER NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    max_attempts INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_priority
ON tasks (status, priority, created_at);

CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    priority INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(category, key)
);

CREATE TABLE IF NOT EXISTS experiences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    success INTEGER NOT NULL,
    message TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    context TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""
