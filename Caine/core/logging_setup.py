"""Logging setup for file logs and systemd journal capture."""

from __future__ import annotations

import logging
import sys

from Caine.config.settings import LoggingSettings


def configure_logging(settings: LoggingSettings) -> logging.Logger:
    """Configure root logging and return the Caine logger."""

    settings.file_path.parent.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, settings.level.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    file_handler = logging.FileHandler(settings.file_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    return logging.getLogger("caine")

