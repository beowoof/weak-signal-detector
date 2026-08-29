from __future__ import annotations

import sys
import threading
from typing import TextIO


class Progress:
    """Operator progress on stderr. JSON results stay on stdout."""

    def __init__(self, *, enabled: bool = True, stream: TextIO | None = None) -> None:
        self.enabled = enabled
        self.stream = stream or sys.stderr
        self._lock = threading.Lock()

    def status(self, message: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            self.stream.write("\r" + _fit(message))
            self.stream.flush()

    def line(self, message: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            # Erase the rest of the status line so leftovers like "TOM" / dates
            # do not stick to the shorter summary.
            self.stream.write("\r" + message + "\033[K\n")
            self.stream.flush()


SILENT = Progress(enabled=False)


def _fit(message: str, width: int = 100) -> str:
    text = message.replace("\n", " ")
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text.ljust(width)
