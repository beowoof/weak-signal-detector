from __future__ import annotations

import json
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO


class Progress:
    """Operator progress on stderr, plus an optional JSON snapshot for the desk."""

    def __init__(self, *, enabled: bool = True, stream: TextIO | None = None) -> None:
        self.enabled = enabled
        self.stream = stream or sys.stderr
        self.paths: list[Path] = []
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {}
        self._started = time.monotonic()
        self._started_at = datetime.now(UTC)
        self._pulse_stop = threading.Event()
        self._pulse_thread: threading.Thread | None = None
        self._last_line_at = 0.0

    def bind(self, *paths: Path) -> None:
        self.paths = [path for path in paths if path is not None]
        for path in self.paths:
            path.parent.mkdir(parents=True, exist_ok=True)
        self._write()

    def update(self, **fields: Any) -> None:
        with self._lock:
            for key, value in fields.items():
                if value is None:
                    self._state.pop(key, None)
                else:
                    self._state[key] = value
            self._write()
            self._redraw()

    def status(self, message: str, **fields: Any) -> None:
        self.update(message=message, **fields)
        if not self.enabled:
            return
        with self._lock:
            now = time.monotonic()
            if now - self._last_line_at >= 60:
                self.stream.write("\n")
                self.stream.flush()
                self._last_line_at = now

    def line(self, message: str, **fields: Any) -> None:
        self.update(message=message, **fields)
        if not self.enabled:
            return
        with self._lock:
            self.stream.write("\r" + message + "\033[K\n")
            self.stream.flush()
            self._last_line_at = time.monotonic()

    def start_pulse(self) -> None:
        if self._pulse_thread is not None:
            return
        self._pulse_stop.clear()

        def run() -> None:
            while not self._pulse_stop.wait(2):
                with self._lock:
                    self._write()
                    self._redraw()

        self._pulse_thread = threading.Thread(target=run, name="wsd-progress", daemon=True)
        self._pulse_thread.start()

    def stop_pulse(self) -> None:
        self._pulse_stop.set()
        thread = self._pulse_thread
        self._pulse_thread = None
        if thread is not None:
            thread.join(timeout=1)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot()

    def _snapshot(self) -> dict[str, Any]:
        elapsed = int(time.monotonic() - self._started)
        payload = {
            "started_at": self._started_at.isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "elapsed_s": elapsed,
            "elapsed": format_elapsed(elapsed),
            **self._state,
        }
        return payload

    def _redraw(self) -> None:
        if not self.enabled:
            return
        self.stream.write("\r" + _fit(self._terminal_line()) + "\033[K")
        self.stream.flush()

    def _terminal_line(self) -> str:
        state = self._state
        parts = [
            state.get("source") or "collect",
            state.get("window") or "",
            _fraction(state.get("day_index"), state.get("day_count"), state.get("day")),
            state.get("aoi") or "",
            state.get("tile") or "",
        ]
        bar = _bar(state.get("bytes"), state.get("total_bytes"))
        if bar:
            parts.append(bar)
        elif state.get("step"):
            parts.append(str(state["step"]))
        if state.get("stalled"):
            parts.append("STALLED")
        parts.append(format_elapsed(int(time.monotonic() - self._started)))
        line = " ".join(str(part) for part in parts if part)
        return line or str(state.get("message") or "collect")

    def _write(self) -> None:
        if not self.paths:
            return
        payload = self._snapshot()
        text = json.dumps(payload, indent=2) + "\n"
        for path in self.paths:
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)


SILENT = Progress(enabled=False)


def format_elapsed(seconds: int) -> str:
    hours, rem = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def load_collect_progress(project_root: Path) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    now = datetime.now(UTC)
    for path in sorted(project_root.glob("scenarios/*/collect_progress.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        updated = _parse_dt(payload.get("updated_at"))
        age = (now - updated).total_seconds() if updated else 10**9
        payload["scenario_id"] = payload.get("scenario_id") or path.parent.name
        payload["path"] = str(path)
        payload["age_s"] = int(age)
        payload["stale"] = age > 20
        payload["stalled"] = bool(payload.get("stalled")) or age > 90
        runs.append(payload)
    runs.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    active = next((item for item in runs if not item["stale"]), None)
    return {"runs": runs, "active": active}


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _fraction(index: Any, count: Any, label: Any) -> str:
    if index and count:
        text = f"{index}/{count}"
        return f"{text} {label}" if label else text
    return str(label or "")


def _fmt_bytes(size: int) -> str:
    if size >= 1_000_000:
        return f"{size / 1_000_000:.1f}MB"
    if size >= 1_000:
        return f"{size / 1_000:.0f}KB"
    return f"{size}B"


def _bar(got: Any, total: Any, width: int = 26) -> str:
    try:
        done = int(got or 0)
        size = int(total or 0)
    except (TypeError, ValueError):
        return ""
    if size <= 0:
        return _fmt_bytes(done) if done else ""
    frac = min(1.0, max(0.0, done / size))
    filled = int(round(width * frac))
    body = "#" * filled + "." * (width - filled)
    return f"[{body}] {int(frac * 100):3d}% {_fmt_bytes(done)}/{_fmt_bytes(size)}"


def _fit(message: str, width: int = 140) -> str:
    text = message.replace("\n", " ")
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text

