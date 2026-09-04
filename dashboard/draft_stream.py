"""Per-request progress stream; no persistent queue or resumable job claim."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any


def draft_events(run: Callable[..., dict[str, Any]], *, heartbeat: float = 2) -> Iterator[str]:
    """Run once, sending stages and heartbeats without exposing draft text early.

    Disconnecting stops observation, not the worker. The caller must not retry
    automatically: model generation and file writes may still be in progress.
    """
    job_id = "Job-" + uuid.uuid4().hex[:12]
    started = time.monotonic()
    events: queue.Queue[dict[str, Any]] = queue.Queue()

    def progress(stage: str, completed: int) -> None:
        events.put({"type": "progress", "stage": stage, "completed": completed, "total": 5})

    def worker() -> None:
        try:
            result = run(progress=progress)
            events.put({"type": "result", "result": result})
        except KeyError:
            events.put({"type": "error", "status": 404, "detail": "Unknown notice"})
        except (ValueError, OSError) as exc:
            events.put({"type": "error", "status": 400, "detail": str(exc)})
        except Exception:
            logging.getLogger(__name__).exception("Draft %s failed", job_id)
            events.put({"type": "error", "status": 500, "detail": "Draft failed; check API logs"})

    state = {"type": "progress", "stage": "Starting", "completed": 0, "total": 5}

    def encode(event: dict) -> str:
        return (
            json.dumps({**event, "job_id": job_id, "elapsed_s": int(time.monotonic() - started)})
            + "\n"
        )

    yield encode(state)
    threading.Thread(target=worker, name=job_id, daemon=True).start()
    while True:
        try:
            event = events.get(timeout=heartbeat)
        except queue.Empty:
            event = state
        if event["type"] == "progress":
            state = event
        yield encode(event)
        if event["type"] in {"result", "error"}:
            return
