from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

from wsf.progress import SILENT, Progress
from wsf.types import Observation


@dataclass(frozen=True)
class PullRequest:
    source: str
    series_id: str
    scenario_id: str
    window_id: str
    start: date
    end: date
    queries: Any
    aois: list[dict[str, Any]] = field(default_factory=list)
    timezone: str | None = None
    retrieved_at: datetime | None = None
    output_dir: Path | None = None
    max_workers: int = 8
    progress: Progress | None = None

    def log(self) -> Progress:
        return self.progress or SILENT


@dataclass
class ConnectorResult:
    item: dict[str, Any]
    observations: list[Observation]
    requests: list[dict[str, Any]]


class Connector(Protocol):
    source: str

    def pull(self, request: PullRequest) -> ConnectorResult: ...


def observation_payload(observation: Observation) -> dict[str, Any]:
    return json.loads(observation.model_dump_json())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def relative_under(directory: Path, path: Path) -> str:
    return str(path.relative_to(directory))


def collection_item(
    *,
    source: str,
    window_id: str,
    series_id: str,
    coverage: float,
    provenance_complete: bool,
    contains_post_cutoff_material: bool,
    checksum: str,
    n_expected: int,
    n_ok: int,
    n_missing: int,
    n_source_down: int,
    observations_path: str | None,
    provenance_path: str | None,
    not_applicable: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "item_id": f"{source}:{window_id}",
        "source": source,
        "window_id": window_id,
        "series_id": series_id,
        "coverage": coverage,
        "provenance_complete": provenance_complete,
        "contains_post_cutoff_material": contains_post_cutoff_material,
        "mode": "live",
        "checksum": checksum,
        "n_expected": n_expected,
        "n_ok": n_ok,
        "n_missing": n_missing,
        "n_source_down": n_source_down,
        "observations": observations_path,
        "provenance": provenance_path,
        "not_applicable": not_applicable,
        "notes": notes,
    }
