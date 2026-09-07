"""Atomic local command receipts; no automatic replay of uncertain actions."""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException


class JobHistory:
    def __init__(self, root: Path):
        self.directory = root / "scenarios" / ".desk-jobs"
        self.owner = f"{os.getpid()}:{uuid.uuid4().hex}"
        self.lock = threading.Lock()

    def save(self, job: dict):
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.lock:
            path = self.directory / f"{job['id']}.json"
            if path.exists() and job["state"] == "running":
                existing = json.loads(path.read_text())
                if existing["state"] != "running":
                    return
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(job, default=str), encoding="utf-8")
            temporary.replace(path)

    def start(self, action: str, inputs: dict) -> dict:
        job = {
            "id": uuid.uuid4().hex,
            "action": action,
            "inputs": inputs,
            "owner": self.owner,
            "state": "running",
            "started_at": datetime.now(UTC).isoformat(),
        }
        self.save(job)
        return job

    def read(self, job_id: str):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise HTTPException(400, "Invalid job identifier")
        path = self.directory / f"{job_id}.json"
        if not path.is_file():
            raise HTTPException(404, "Unknown job")
        job = json.loads(path.read_text())
        if job["state"] == "running" and job.get("owner") != self.owner:
            job = {
                **job,
                "state": "unknown",
                "error": (
                    "Execution belongs to a previous API session. Inspect outputs before "
                    "planning another run; it will not be retried automatically."
                ),
            }
        return job

    def list(self):
        paths = sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [self.read(path.stem) for path in paths[:100]]

    def call(self, action: str, inputs: dict, function):
        job = self.start(action, inputs)
        try:
            result = function()
            job.update(state="completed", result=result)
            return result
        except Exception as exc:
            job.update(state="failed", error=str(getattr(exc, "detail", exc)))
            raise
        finally:
            job["finished_at"] = datetime.now(UTC).isoformat()
            self.save(job)
