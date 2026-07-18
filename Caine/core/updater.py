"""Git-based atomic self-update system."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from Caine.config.settings import UpdateSettings


@dataclass(slots=True)
class CommandResult:
    """Completed process result."""

    return_code: int
    stdout: str
    stderr: str


class AsyncCommandRunner:
    """Run subprocesses without blocking the event loop."""

    async def run(
        self,
        command: list[str],
        cwd: Path | None = None,
    ) -> CommandResult:
        """Execute command and capture output."""

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return CommandResult(
            return_code=process.returncode,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )


@dataclass(slots=True)
class Updater:
    """Check, test, and atomically switch to new versions."""

    settings: UpdateSettings
    logger: logging.Logger
    runner: AsyncCommandRunner

    async def check_and_update(self) -> bool:
        """Apply an update when tests pass."""

        previous_target = self._current_target()
        await self._prepare_update_tree()
        changed = await self._pull_or_clone()
        if not changed:
            self.logger.debug("No update available")
            return False
        try:
            await self._install_dependencies()
            await self._run_tests()
            await self._probe_startup()
            self._switch_symlink(self.settings.update_dir)
            await self._write_metadata(previous_target)
            self.logger.info("Updated Caine to %s", self.settings.update_dir)
            return True
        except Exception:
            if previous_target is not None:
                self._switch_symlink(previous_target)
            raise

    async def _prepare_update_tree(self) -> None:
        self.settings.update_dir.parent.mkdir(parents=True, exist_ok=True)

    async def _pull_or_clone(self) -> bool:
        if not (self.settings.update_dir / ".git").exists():
            if self.settings.update_dir.exists():
                shutil.rmtree(self.settings.update_dir)
            result = await self.runner.run(
                [
                    "git",
                    "clone",
                    "--branch",
                    self.settings.branch,
                    self.settings.repository_url,
                    str(self.settings.update_dir),
                ],
            )
            self._require_success(result, "git clone")
            return True

        before = await self.runner.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.settings.update_dir,
        )
        self._require_success(before, "git rev-parse before")
        fetch = await self.runner.run(
            ["git", "fetch", "origin", self.settings.branch],
            cwd=self.settings.update_dir,
        )
        self._require_success(fetch, "git fetch")
        reset = await self.runner.run(
            ["git", "reset", "--hard", f"origin/{self.settings.branch}"],
            cwd=self.settings.update_dir,
        )
        self._require_success(reset, "git reset")
        after = await self.runner.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.settings.update_dir,
        )
        self._require_success(after, "git rev-parse after")
        return before.stdout.strip() != after.stdout.strip()

    async def _install_dependencies(self) -> None:
        requirements = (
            self.settings.update_dir / self.settings.requirements_file
        )
        if not requirements.exists():
            return
        result = await self.runner.run(
            [
                "python",
                "-m",
                "pip",
                "install",
                "-r",
                str(requirements),
            ],
            cwd=self.settings.update_dir,
        )
        self._require_success(result, "pip install")

    async def _run_tests(self) -> None:
        result = await self.runner.run(
            self.settings.test_command,
            cwd=self.settings.update_dir,
        )
        self._require_success(result, "tests")

    async def _probe_startup(self) -> None:
        result = await self.runner.run(
            self.settings.startup_probe_command,
            cwd=self.settings.update_dir,
        )
        self._require_success(result, "startup probe")

    def _switch_symlink(self, target: Path) -> None:
        temporary = self.settings.symlink_path.with_name(
            f"{self.settings.symlink_path.name}.next",
        )
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
        os.symlink(target, temporary, target_is_directory=True)
        os.replace(temporary, self.settings.symlink_path)

    def _current_target(self) -> Path | None:
        if self.settings.symlink_path.is_symlink():
            return self.settings.symlink_path.resolve()
        if self.settings.current_dir.exists():
            return self.settings.current_dir
        return None

    async def _write_metadata(self, previous_target: Path | None) -> None:
        current_revision = await self.runner.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.settings.update_dir,
        )
        self._require_success(current_revision, "git rev-parse metadata")
        metadata = {
            "current_version": current_revision.stdout.strip(),
            "current_path": str(self.settings.update_dir),
            "previous_path": str(previous_target) if previous_target else None,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        path = Path(self.settings.metadata_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            path.write_text,
            json.dumps(metadata, indent=2),
            "utf-8",
        )

    def _require_success(self, result: CommandResult, action: str) -> None:
        if result.return_code == 0:
            return
        self.logger.error("%s failed: %s", action, result.stderr)
        raise RuntimeError(f"{action} failed")
