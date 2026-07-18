"""Reasoning router for local and remote language models."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from Caine.config.settings import ReasoningSettings


class RemoteReasoner(Protocol):
    """Protocol for a remote reasoning client."""

    async def reason(self, prompt: str, context: dict[str, Any]) -> str | None:
        """Return a remote answer when available."""


@dataclass(slots=True)
class Reasoning:
    """Route simple prompts locally and complex prompts remotely."""

    settings: ReasoningSettings
    remote_client: RemoteReasoner
    logger: logging.Logger

    async def decide(self, prompt: str, context: dict[str, Any]) -> str:
        """Return an autonomous decision."""

        complexity = self._estimate_complexity(prompt, context)
        if complexity >= self.settings.complexity_threshold:
            remote = await self.remote_client.reason(prompt, context)
            if remote:
                return remote
        return self._local_decision(prompt, context)

    def _estimate_complexity(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> int:
        words = len(prompt.split())
        context_weight = len(str(context)) // 80
        return words + context_weight

    def _local_decision(self, prompt: str, context: dict[str, Any]) -> str:
        self.logger.debug(
            "Using local model '%s' for prompt: %s",
            self.settings.local_model_name,
            prompt,
        )
        pending = context.get("pending_tasks", 0)
        if pending:
            return "process_pending_task"
        return "observe_and_checkpoint"
