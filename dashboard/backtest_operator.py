"""Bounded backtest plans; explicit inputs, no arbitrary commands or shell execution."""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from dashboard.job_history import JobHistory
from dashboard.scenario_workspace import safe_file, scenario_dir
from wsf.progress import Progress
from wsf.scenario import create_scenario, load_scenario, load_status, require_collection_ready
from wsf.workflow import STAGES, run_desk_workflow

LOCK = threading.Lock()


class PlanBody(BaseModel):
    scenario: str
    start: Literal["validate", "collect", "review", "measure", "emit"] = "validate"
    through: Literal["validate", "collect", "review", "measure", "emit"] = "emit"
    only: list[str] = Field(default_factory=list)
    focus: str = ""
    mock: bool = False
    exploratory: bool = True
    source_workers: int = Field(default=4, ge=1, le=8)
    revision: str = ""


def plan(root: Path, body: PlanBody) -> dict:
    directory = scenario_dir(root / "scenarios", body.scenario)
    config = load_scenario(root, body.scenario)
    require_collection_ready(config)
    start, end = STAGES.index(body.start), STAGES.index(body.through)
    if start > end:
        raise ValueError("First stage must precede the last stage")
    if body.focus and not start <= 1 <= end:
        raise ValueError("Focused gap repair requires collection")
    if body.only and not start <= 1 <= end:
        raise ValueError("Source selection only applies to collection")
    if any(s not in config.sources or not config.sources[s].enabled for s in body.only):
        raise ValueError("Choose only enabled sources from this scenario")
    files = [directory / "scenario.json", directory / "status.json", directory / "freeze.json"]
    files += sorted((root / "config").glob("*.yaml"))
    status = load_status(root, body.scenario)
    if body.focus:
        focus = safe_file(directory, body.focus)
        if not body.focus.startswith("reviews/") or focus.name != "missing.json":
            raise ValueError("Choose a saved missing.json review from this scenario")
        files.append(focus)
    fingerprint = hashlib.sha256()
    for path in files:
        fingerprint.update(str(path.relative_to(root)).encode())
        fingerprint.update(path.read_bytes() if path.exists() else b"absent")
    fingerprint.update(body.model_dump_json(exclude={"revision"}).encode())
    return {
        "revision": fingerprint.hexdigest(),
        "scenario": body.scenario,
        "stages": list(STAGES[start : end + 1]),
        "inputs": status,
        "windows": [config.incident.model_dump(mode="json")]
        + [w.model_dump(mode="json") for w in config.controls],
        "sources": body.only or [s for s, c in config.sources.items() if c.enabled],
        "mode": "Synthetic rehearsal" if body.mock else "Historical backtest · real sources",
        "measurement": "Exploratory unless matching real freeze exists"
        if body.exploratory
        else "Matching real freeze required",
        "options": body.model_dump(exclude={"revision"}),
    }


def operator_router(root: Path, history: JobHistory) -> APIRouter:
    router = APIRouter()
    jobs: dict[str, dict] = {}

    @router.post("/api/operator/plan")
    def preview(body: PlanBody):
        try:
            return plan(root, body)
        except (ValueError, OSError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/api/operator/create")
    def create(body: PlanBody):
        try:
            create_scenario(root, body.scenario)
            return {
                "scenario": body.scenario,
                "next": "Complete required fields in the scenario editor, then validate.",
            }
        except (ValueError, OSError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/api/operator/run")
    def run(body: PlanBody):
        if not LOCK.acquire(blocking=False):
            raise HTTPException(
                409, "Another backtest is running; inspect it before starting another"
            )
        try:
            current = preview(body)
            if not body.revision or current["revision"] != body.revision:
                raise HTTPException(
                    409, "Inputs or options changed. Preview a new plan before running."
                )
            receipt = history.start("backtest", body.model_dump())
            job_id = receipt["id"]
            progress = Progress(enabled=False)
            jobs[job_id] = {
                **receipt,
                "plan": current,
                "state": "running",
                "started_at": datetime.now(UTC).isoformat(),
                "progress": progress,
            }
        except BaseException:
            LOCK.release()
            raise

        def work():
            job = jobs[job_id]
            try:
                result = run_desk_workflow(
                    root,
                    body.scenario,
                    from_stage=body.start,
                    through=body.through,
                    only=body.only or None,
                    focus_path=root / "scenarios" / body.scenario / body.focus
                    if body.focus
                    else None,
                    mock=body.mock,
                    exploratory=body.exploratory,
                    source_workers=body.source_workers,
                    progress=progress,
                )
                job.update(state=result["status"], result=result)
            except Exception as exc:
                job.update(state="failed", error=str(exc))
            finally:
                job["finished_at"] = datetime.now(UTC).isoformat()
                history.save({**job, "progress": progress.snapshot()})
                LOCK.release()

        threading.Thread(target=work, daemon=True).start()
        return {"id": job_id}

    @router.get("/api/operator/job/{job_id}")
    def job(job_id: str):
        if job_id not in jobs:
            return history.read(job_id)
        value = jobs[job_id]
        if value.get("finished_at"):
            return history.read(job_id)
        snapshot = {**value, "progress": value["progress"].snapshot()}
        history.save(snapshot)
        return snapshot

    @router.get("/api/operator/jobs")
    def list_jobs():
        return {"jobs": history.list()}

    return router
