"""JSONL event logger for episode traces."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class EventLogger:
    """Writes structured events to a JSONL file."""

    def __init__(self, log_path: str | Path) -> None:
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "a")
        self._start = time.time()

    def log(self, event: dict[str, Any]) -> None:
        """Write an event with timestamp."""
        record = {
            "ts": time.time() - self._start,
            "wall": time.time(),
            **event,
        }
        self._file.write(json.dumps(record, default=str) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    @property
    def path(self) -> Path:
        return self._path

    def __enter__(self) -> EventLogger:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def make_event_callback(logger: EventLogger):
    """Create an event callback function for Episode."""

    def callback(event: dict[str, Any]) -> None:
        logger.log(event)

    return callback
