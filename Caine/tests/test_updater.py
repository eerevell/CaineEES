"""Tests for self-updater."""

from __future__ import annotations

from pathlib import Path

import pytest

from Caine.core.updater import CommandResult, Updater
from Caine.tests.conftest import make_settings, make_test_logger


class FakeRunner:
    def __init__(self, fail_tests: bool = False) -> None:
        self.commands: list[list[str]] = []
        self.fail_tests = fail_tests
        self.rev_parse_calls = 0

    async def run(
        self,
        command: list[str],
        cwd: Path | None = None,
    ) -> CommandResult:
        self.commands.append(command)
        if command == ["git", "rev-parse", "HEAD"]:
            self.rev_parse_calls += 1
            revision = "old" if self.rev_parse_calls == 1 else "new"
            return CommandResult(0, f"{revision}\n", "")
        if command[:3] == ["python", "-m", "pytest"] and self.fail_tests:
            return CommandResult(1, "", "tests failed")
        return CommandResult(0, "ok\n", "")


@pytest.mark.asyncio
async def test_updater_keeps_symlink_when_tests_fail(tmp_path) -> None:
    settings = make_settings(tmp_path)
    settings.update.update_dir.mkdir(parents=True)
    (settings.update.update_dir / ".git").mkdir()
    (settings.update.update_dir / "requirements.txt").write_text("", "utf-8")
    runner = FakeRunner(fail_tests=True)
    updater = Updater(settings.update, make_test_logger(), runner)

    with pytest.raises(RuntimeError):
        await updater.check_and_update()

    assert not settings.update.symlink_path.exists()
