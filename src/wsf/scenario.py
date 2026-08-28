from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from wsf.protocol import canonical_sha256

SCENARIO_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


class WindowConfig(BaseModel):
    id: str
    start: date | None = None
    end: date | None = None
    target_start: date | None = None
    target_end: date | None = None
    lookback_days: int = Field(default=120, ge=20, le=730)
    selection_reason: str = ""

    @model_validator(mode="after")
    def dates_consistent(self) -> WindowConfig:
        if (self.start is None) != (self.end is None):
            raise ValueError(f"{self.id}: start and end must both be set or both be null")
        if self.start and self.end and self.start > self.end:
            raise ValueError(f"{self.id}: start must not be after end")
        if (self.target_start is None) != (self.target_end is None):
            raise ValueError(f"{self.id}: target dates must both be set or both be null")
        if self.target_start and self.target_end and self.target_start > self.target_end:
            raise ValueError(f"{self.id}: target_start must not be after target_end")
        return self


class ActorConfig(BaseModel):
    focal: str | None = None
    counterparts: list[str] = Field(default_factory=list)


class SourceConfig(BaseModel):
    enabled: bool = True


class QueryConfig(BaseModel):
    wiki_titles: list[str] = Field(default_factory=list)
    cameo_actor: str | None = None
    cameo_root_codes: list[str] = Field(default_factory=lambda: ["01", "02", "04", "13"])
    fred_series: str | None = None
    facility_actor: str | None = None


class CorpusGates(BaseModel):
    minimum_daily_coverage: float = Field(default=0.95, ge=0, le=1)
    maximum_incident_control_coverage_difference: float = Field(default=0.05, ge=0, le=1)
    minimum_valid_viirs_fraction: float = Field(default=0.70, ge=0, le=1)
    require_complete_provenance: bool = True
    forbid_post_cutoff_material: bool = True
    forbidden_outcome_terms: list[str] = Field(default_factory=list)


class InterpretationConfig(BaseModel):
    enabled: bool = True
    model: str = "qwen3.8:27b-mlx"
    repeats: int = Field(default=5, ge=1, le=20)


class ScenarioConfig(BaseModel):
    schema_version: Literal[1] = 1
    scenario_id: str
    status: Literal["draft"] = "draft"
    purpose: Literal["development_showcase", "held_out", "rehearsal"] = "development_showcase"
    research_question: str
    actors: ActorConfig
    incident: WindowConfig
    controls: list[WindowConfig] = Field(default_factory=list)
    sources: dict[str, SourceConfig]
    queries: QueryConfig
    corpus_gates: CorpusGates = Field(default_factory=CorpusGates)
    interpretation: InterpretationConfig = Field(default_factory=InterpretationConfig)

    @model_validator(mode="after")
    def scenario_consistent(self) -> ScenarioConfig:
        if not SCENARIO_NAME.fullmatch(self.scenario_id):
            raise ValueError("scenario_id must be a lowercase kebab-case name")
        window_ids = [self.incident.id, *(item.id for item in self.controls)]
        if len(window_ids) != len(set(window_ids)):
            raise ValueError("window ids must be unique")
        return self


def scenario_directory(project_root: Path, scenario_id: str) -> Path:
    if not SCENARIO_NAME.fullmatch(scenario_id):
        raise ValueError("scenario name must be lowercase kebab-case")
    return project_root / "scenarios" / scenario_id


def create_scenario(project_root: Path, scenario_id: str) -> Path:
    directory = scenario_directory(project_root, scenario_id)
    directory.mkdir(parents=True, exist_ok=False)
    for relative in ("corpus", "reviews", "measurement", "interpretation", "reports"):
        (directory / relative).mkdir()

    scenario = ScenarioConfig(
        scenario_id=scenario_id,
        research_question=(
            "Do correlated weak public signals add information to strategic-intent triage?"
        ),
        actors=ActorConfig(),
        incident=WindowConfig(id="incident"),
        controls=[WindowConfig(id="same-period-prior-year")],
        sources={source: SourceConfig() for source in ("gdelt", "wikipedia", "alfred", "viirs")},
        queries=QueryConfig(),
        corpus_gates=CorpusGates(
            forbidden_outcome_terms=["full-scale invasion", "2022 russian invasion of ukraine"]
        ),
    )
    _write_json(directory / "scenario.json", scenario.model_dump(mode="json"))
    now = datetime.now(UTC).isoformat()
    status = {
        "scenario_id": scenario_id,
        "phase": "draft",
        "created_at": now,
        "updated_at": now,
        "active_collection_id": None,
        "active_review_id": None,
        "freeze_id": None,
    }
    _write_json(directory / "status.json", status)
    append_history(directory, "scenario_created", {"scenario_hash": scenario_hash(scenario)})
    return directory


def load_scenario(project_root: Path, scenario_id: str) -> ScenarioConfig:
    path = scenario_directory(project_root, scenario_id) / "scenario.json"
    return ScenarioConfig.model_validate_json(path.read_text(encoding="utf-8"))


def load_status(project_root: Path, scenario_id: str) -> dict[str, Any]:
    path = scenario_directory(project_root, scenario_id) / "status.json"
    return json.loads(path.read_text(encoding="utf-8"))


def save_status(project_root: Path, scenario_id: str, status: dict[str, Any]) -> None:
    status["updated_at"] = datetime.now(UTC).isoformat()
    _write_json(scenario_directory(project_root, scenario_id) / "status.json", status)


def require_collection_ready(scenario: ScenarioConfig) -> None:
    gaps: list[str] = []
    if not scenario.actors.focal:
        gaps.append("actors.focal")
    if not scenario.actors.counterparts:
        gaps.append("actors.counterparts")
    if scenario.incident.start is None or scenario.incident.end is None:
        gaps.append("incident dates")
    if scenario.incident.target_start is None or scenario.incident.target_end is None:
        gaps.append("incident target dates")
    if not scenario.incident.selection_reason:
        gaps.append("incident selection_reason")
    if not scenario.controls:
        gaps.append("at least one control")
    for control in scenario.controls:
        if control.start is None or control.end is None:
            gaps.append(f"control dates: {control.id}")
        if not control.selection_reason:
            gaps.append(f"control selection_reason: {control.id}")
    if not scenario.queries.wiki_titles:
        gaps.append("queries.wiki_titles")
    if not scenario.queries.cameo_actor:
        gaps.append("queries.cameo_actor")
    if not scenario.queries.facility_actor:
        gaps.append("queries.facility_actor")
    if gaps:
        raise ValueError("scenario is not collection-ready: " + ", ".join(gaps))


def scenario_hash(scenario: ScenarioConfig) -> str:
    return canonical_sha256(scenario.model_dump(mode="json"))


def freeze_scenario(
    project_root: Path,
    scenario_id: str,
    *,
    allow_rehearsal: bool = False,
) -> Path:
    directory = scenario_directory(project_root, scenario_id)
    scenario = load_scenario(project_root, scenario_id)
    status = load_status(project_root, scenario_id)
    review_id = status.get("active_review_id")
    collection_id = status.get("active_collection_id")
    if not review_id or not collection_id:
        raise ValueError("scenario requires an active collection and review before freeze")
    review_path = directory / "reviews" / review_id / "decision.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    current_hash = scenario_hash(scenario)
    if review.get("scenario_hash") != current_hash:
        raise ValueError("scenario changed after review; collect and review a new corpus revision")
    accepted = {"go_candidate"}
    if allow_rehearsal:
        accepted.add("go_candidate_rehearsal")
    if review.get("decision") not in accepted:
        raise ValueError(f"review decision {review.get('decision')} cannot be frozen")

    freeze_id = f"freeze-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    value = {
        "freeze_id": freeze_id,
        "scenario_id": scenario_id,
        "scenario_hash": current_hash,
        "collection_id": collection_id,
        "review_id": review_id,
        "rehearsal": review.get("decision") == "go_candidate_rehearsal",
        "created_at": datetime.now(UTC).isoformat(),
    }
    path = directory / "freeze.json"
    _write_json(path, value)
    status.update({"phase": "frozen", "freeze_id": freeze_id})
    save_status(project_root, scenario_id, status)
    append_history(directory, "scenario_frozen", value)
    return path


def append_history(directory: Path, event: str, details: dict[str, Any]) -> None:
    record = {"ts": datetime.now(UTC).isoformat(), "event": event, "details": details}
    with (directory / "history.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
