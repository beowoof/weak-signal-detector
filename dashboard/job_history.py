"""Atomic local command receipts; no automatic replay of uncertain actions."""

from __future__ import annotations

import hashlib
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
        self.lock = threading.RLock()

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
        request_id = inputs.get("request_id")
        ident = (
            hashlib.sha256(str(request_id).encode()).hexdigest()[:32]
            if request_id
            else uuid.uuid4().hex
        )
        if (self.directory / f"{ident}.json").exists():
            prior = self.read(ident)
            if prior["action"] != action or prior["inputs"] != inputs:
                raise HTTPException(409, "This request ID belongs to different inputs")
            return {**prior, "_reused": True}
        job = {
            "id": ident,
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

    def launch(self, action, inputs, function):
        with self.lock:
            job = self.start(action, inputs)
            if job.get("_reused"):
                return {
                    "id": job["id"],
                    "reused": True,
                    "state": job.get("state", "unknown"),
                }
            # Single writer per notice for model/research jobs in this API session.
            active = [
                j
                for j in self.list()
                if j["id"] != job["id"]
                and j["state"] == "running"
                and j["inputs"].get("scenario") == inputs.get("scenario")
                and j["inputs"].get("notice_id") == inputs.get("notice_id")
            ]
            if active:
                job.update(
                    state="failed",
                    error="Another job is running for this notice. Reconnect in command history.",
                )
                self.save(job)
                raise HTTPException(409, job["error"])

        def work():
            def progress(stage, completed):
                job["progress"] = {"stage": stage, "completed": completed}
                self.save(job)

            try:
                job.update(result=function(progress=progress), state="completed")
            except Exception as exc:
                job.update(state="failed", error=str(exc))
            finally:
                job["finished_at"] = datetime.now(UTC).isoformat()
                self.save(job)

        threading.Thread(target=work, daemon=True).start()
        return {"id": job["id"], "reused": False, "state": "running"}
