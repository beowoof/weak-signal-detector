"""Scenario contract editing and bounded, read-only collection artefact access."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import threading
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError

from wsf.scenario import SCENARIO_NAME, ScenarioConfig, require_collection_ready

MAX_BYTES = 1_000_000
GROUPS = {"corpus", "reviews", "measurement", "interpretation", "reports", "notices"}
ROOT_FILES = {"status.json", "history.jsonl", "freeze.json", "desk_pin.json", "collect_progress.json"}
SAVE_LOCK = threading.Lock()


class ContractBody(BaseModel):
    scenario: str
    text: str = Field(max_length=MAX_BYTES)
    revision: str = ""


def scenario_dir(root: Path, scenario: str) -> Path:
    if not SCENARIO_NAME.fullmatch(scenario):
        raise HTTPException(400, "Invalid scenario identifier")
    path = root / scenario
    if path.is_symlink() or not path.is_dir():
        raise HTTPException(404, "Unknown scenario")
    return path


def safe_file(directory: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if parts.is_absolute() or not parts.parts or any(p in {".", ".."} for p in parts.parts):
        raise HTTPException(400, "Invalid file path")
    path = directory
    for part in parts.parts:
        path = path / part
        if path.is_symlink():
            raise HTTPException(400, "Symlink artefacts are not exposed")
    if not path.resolve().is_relative_to(directory.resolve()) or not path.is_file():
        raise HTTPException(404, "File not found")
    return path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(text: str):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError(f"Duplicate JSON key: {key}")
            obj[key] = value
        return obj

    def invalid(value):
        raise ValueError(f"Non-finite JSON value: {value}")

    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Non-finite JSON number: {value}")
        return number

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite)


def validate_contract(scenario: str, text: str) -> dict:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise HTTPException(413, "Scenario exceeds the editor size limit")
    try:
        document = strict_json(text)
        config = ScenarioConfig.model_validate(document)
        if config.scenario_id != scenario:
            raise ValueError(
                "scenario_id must match the selected scenario; renaming is not supported"
            )
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc
    warnings = []
    try:
        require_collection_ready(config)
    except ValueError as exc:
        warnings.append(str(exc))
    return {"valid": True, "warnings": warnings}


def contract_payload(directory: Path) -> dict:
    path = safe_file(directory, "scenario.json")
    if path.stat().st_size > MAX_BYTES:
        raise HTTPException(413, "Scenario exceeds the editor size limit")
    data = path.read_bytes()
    return {
        "scenario_id": directory.name,
        "text": data.decode("utf-8"),
        "revision": digest(data),
        "frozen": (directory / "freeze.json").exists(),
    }


def artifact_path(directory: Path, relative: str) -> Path:
    parts = PurePosixPath(relative).parts
    if not parts or (parts[0] not in GROUPS and relative not in ROOT_FILES):
        raise HTTPException(400, "Not a collection artefact")
    path = safe_file(directory, relative)
    if path.suffix not in {".json", ".jsonl", ".md"}:
        raise HTTPException(400, "Unsupported artefact type")
    return path


def preview(path: Path, offset: int, limit: int) -> dict:
    result = {"format": path.suffix[1:], "size": path.stat().st_size, "offset": offset}
    if path.suffix == ".jsonl":
        records, lines, used, more = [], [], 0, False
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            for _ in range(offset):
                # Bounded line reads also protect against malformed giant records.
                line = stream.readline(MAX_BYTES + 1)
                if not line:
                    break
                if len(line) > MAX_BYTES:
                    raise HTTPException(
                        413, "A record exceeds the preview limit; download the file"
                    )
            for index in range(limit):
                line = stream.readline(MAX_BYTES + 1)
                if not line:
                    break
                if len(line) > MAX_BYTES or used + len(line.encode("utf-8")) > MAX_BYTES:
                    if not records:
                        raise HTTPException(
                            413, "A record exceeds the preview limit; download the file"
                        )
                    more = True
                    break
                used += len(line.encode("utf-8"))
                lines.append(line)
                try:
                    records.append(strict_json(line))
                except ValueError as exc:
                    records.append(
                        {"line": offset + index + 1, "parse_error": str(exc), "raw": line.rstrip()}
                    )
            else:
                more = bool(stream.read(1))
        result.update(
            records=records,
            text="".join(lines),
            truncated=more,
            next_offset=offset + len(records) if more else None,
        )
    else:
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        truncated = len(data) > MAX_BYTES
        text = data[:MAX_BYTES].decode("utf-8", errors="replace")
        result.update(text=text, truncated=truncated)
        if path.suffix == ".json" and not truncated:
            try:
                result["data"] = strict_json(text)
            except ValueError as exc:
                result["parse_error"] = str(exc)
    return result


def scenario_router(root: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/api/scenarios")
    def index():
        items = []
        for path in sorted(root.glob("*/scenario.json")):
            try:
                directory = scenario_dir(root, path.parent.name)
                payload = contract_payload(directory)
                try:
                    doc = strict_json(payload["text"])
                    payload["research_question"] = doc.get("research_question", "")
                except (ValueError, AttributeError):
                    payload["research_question"] = "Invalid JSON — open editor to repair"
                payload.pop("text")
                items.append(payload)
            except HTTPException:
                continue
        return {"scenarios": items}

    @router.get("/api/scenario")
    def contract(scenario: str):
        return contract_payload(scenario_dir(root, scenario))

    @router.post("/api/scenario/validate")
    def validate(body: ContractBody):
        scenario_dir(root, body.scenario)
        return validate_contract(body.scenario, body.text)

    @router.post("/api/scenario/save")
    def save(body: ContractBody):
        directory = scenario_dir(root, body.scenario)
        validation = validate_contract(body.scenario, body.text)
        with SAVE_LOCK:
            current = contract_payload(directory)
            if current["frozen"]:
                raise HTTPException(
                    409, "Frozen scenario: create a separate scenario before editing"
                )
            if body.revision != current["revision"]:
                raise HTTPException(
                    409, "Scenario changed on disk. Reload and reconcile your draft before saving"
                )
            path = safe_file(directory, "scenario.json")
            fd, temp_name = tempfile.mkstemp(prefix=".scenario-", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(body.text if body.text.endswith("\n") else body.text + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temp_name, path.stat().st_mode & 0o777)
                os.replace(temp_name, path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            saved = contract_payload(directory)
        return {**saved, **validation}

    @router.get("/api/scenario/artifacts")
    def artifacts(scenario: str):
        directory = scenario_dir(root, scenario)
        items = []
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(directory).as_posix()
            if path.suffix not in {".json", ".jsonl", ".md"} or not path.is_file():
                continue
            try:
                allowed = artifact_path(directory, relative)
            except HTTPException:
                continue
            stat = allowed.stat()
            parts = PurePosixPath(relative).parts
            items.append(
                {
                    "path": relative,
                    "name": path.name,
                    "group": parts[0],
                    "run": parts[1] if len(parts) > 2 else "",
                    "size": stat.st_size,
                    "modified_at": stat.st_mtime,
                }
            )
        return {"scenario_id": scenario, "artifacts": items}

    @router.get("/api/scenario/artifact")
    def artifact(
        scenario: str,
        path: str,
        offset: int = Query(0, ge=0, le=1_000_000),
        limit: int = Query(100, ge=1, le=500),
    ):
        target = artifact_path(scenario_dir(root, scenario), path)
        return {"path": path, **preview(target, offset, limit)}

    @router.get("/api/scenario/artifact/download")
    def download(scenario: str, path: str):
        target = artifact_path(scenario_dir(root, scenario), path)
        return FileResponse(target, media_type="application/octet-stream", filename=target.name)

    return router
