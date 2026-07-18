"""HTTP client for the external compute server."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp


@dataclass(slots=True)
class RemoteReasoningClient:
    """Client used for large-model remote reasoning."""

    api_url: str
    timeout_seconds: float
    logger: logging.Logger

    async def reason(self, prompt: str, context: dict[str, Any]) -> str | None:
        """Return a remote model answer, or None when unavailable."""

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.api_url,
                    json={"prompt": prompt, "context": context},
                ) as response:
                    if response.status >= 400:
                        self.logger.warning(
                            "Remote reasoning failed with HTTP %s",
                            response.status,
                        )
                        return None
                    payload = await response.json()
                    answer = payload.get("answer")
                    return str(answer) if answer is not None else None
        except aiohttp.ClientError as exc:
            self.logger.warning("Remote reasoning unavailable: %s", exc)
            return None
        except TimeoutError:
            self.logger.warning("Remote reasoning timed out")
            return None

