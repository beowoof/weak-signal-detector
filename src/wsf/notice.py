"""notice_v0: immutable cue event plus mutable desk workflow."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from wsf.analysis.coupling import DailyCouplingState, evaluate_window_coupling
from wsf.protocol import load_yaml
from wsf.scenario import load_scenario, load_status, scenario_directory

NOTICE_SCHEMA = "notice_v0"
DEFAULT_POLICY_ID = "coupling_k3_z15_p3"


class CollectionPosture(StrEnum):
    routine = "routine"
    heightened = "heightened"
    focused = "focused"
    surge_review = "surge_review"


class NoticeState(StrEnum):
    new = "new"
    acked = "acked"
    in_packet = "in_packet"
    closed = "closed"


class NoticeTrigger(BaseModel):
    """Facts that caused the notice. Frozen after write."""

    scenario_id: str
    window_id: str
    collection_id: str
    measurement_id: str
    policy_id: str
    policy_params: dict[str, Any]
    created_at: datetime
    start: date
    end: date
    duration_days: int
    days_before_window_end: int
    contributing_domains: list[str]
    contributing_series: list[str]
    observed: dict[str, Any]
    derived: dict[str, Any]
    heuristic: dict[str, Any]
    unknowns: list[str]
    imaging_status_by_day: dict[str, str]
    recommended_posture: CollectionPosture
    recommended_posture_reason: str
    information_environment_snapshot_id: str | None = None


class NoticeWorkflow(BaseModel):
    state: NoticeState = NoticeState.new
    selected_posture: CollectionPosture | None = None
    comments: list[str] = Field(default_factory=list)
    packet_id: str | None = None
    report_id: str | None = None
    closure_rationale: str | None = None
    updated_at: datetime | None = None


class Notice(BaseModel):
    schema_id: Literal["notice_v0"] = NOTICE_SCHEMA
    notice_id: str
    trigger: NoticeTrigger
    workflow: NoticeWorkflow = Field(default_factory=NoticeWorkflow)


def load_notice_policies(project_root: Path) -> dict[str, Any]:
    return load_yaml(project_root / "config" / "notice_policy.yaml")


def default_policy(project_root: Path) -> dict[str, Any]:
    payload = load_notice_policies(project_root)
    for item in payload.get("policies") or []:
        if item.get("default"):
            return item
    raise ValueError("notice_policy.yaml has no default policy")


def notice_id_for(trigger: NoticeTrigger) -> str:
    core = {
        "scenario_id": trigger.scenario_id,
        "measurement_id": trigger.measurement_id,
        "policy_id": trigger.policy_id,
        "window_id": trigger.window_id,
        "start": trigger.start.isoformat(),
        "end": trigger.end.isoformat(),
    }
    digest = hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()[:12]
    return f"notice-{digest}"


def notices_directory(project_root: Path, scenario_id: str) -> Path:
    path = scenario_directory(project_root, scenario_id) / "notices"
    path.mkdir(parents=True, exist_ok=True)
    return path


def notice_path(project_root: Path, scenario_id: str, notice_id: str) -> Path:
    return notices_directory(project_root, scenario_id) / notice_id / "notice.json"


def load_notice(project_root: Path, scenario_id: str, notice_id: str) -> Notice:
    return Notice.model_validate_json(
        notice_path(project_root, scenario_id, notice_id).read_text(encoding="utf-8")
    )


def list_notices(project_root: Path, scenario_id: str) -> list[Notice]:
    root = scenario_directory(project_root, scenario_id) / "notices"
    if not root.is_dir():
        return []
    notices: list[Notice] = []
    for path in sorted(root.glob("*/notice.json")):
        notices.append(Notice.model_validate_json(path.read_text(encoding="utf-8")))
    notices.sort(key=lambda item: (item.trigger.start, item.trigger.end, item.notice_id))
    return notices


def save_notice(project_root: Path, notice: Notice, *, overwrite_trigger: bool = False) -> Path:
    path = notice_path(project_root, notice.trigger.scenario_id, notice.notice_id)
    if path.is_file() and not overwrite_trigger:
        existing = Notice.model_validate_json(path.read_text(encoding="utf-8"))
        existing.workflow = notice.workflow
        path.write_text(existing.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(notice.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def emit_notices_for_measurement(
    project_root: Path,
    scenario_id: str,
    *,
    measurement_id: str | None = None,
    policy_id: str | None = None,
) -> list[Notice]:
    """Create missing notices from K≥3 coupling episodes. Never rewrite trigger facts."""
    status = load_status(project_root, scenario_id)
    measure_id = measurement_id or status.get("active_measurement_id")
    collection_id = status.get("active_collection_id") or ""
    if not measure_id:
        raise ValueError(f"{scenario_id}: no active measurement")
    measure_dir = scenario_directory(project_root, scenario_id) / "measurement" / measure_id
    features_path = measure_dir / "features.jsonl"
    if not features_path.is_file():
        raise ValueError(f"missing features: {features_path}")
    features = [
        json.loads(line)
        for line in features_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    policy = default_policy(project_root)
    if policy_id:
        match = next(
            (
                item
                for item in load_notice_policies(project_root)["policies"]
                if item["id"] == policy_id
            ),
            None,
        )
        if match is None:
            raise ValueError(f"unknown notice policy {policy_id}")
        policy = match
    if policy.get("implemented") is False:
        raise ValueError(f"policy {policy['id']} is not implemented")
    scenario = load_scenario(project_root, scenario_id)
    window_ends: dict[str, date] = {}
    if scenario.incident.end:
        window_ends[scenario.incident.id] = scenario.incident.end
    for window in scenario.controls:
        if window.end:
            window_ends[window.id] = window.end

    created_at = datetime.now(UTC)
    emitted: list[Notice] = []
    windows = sorted({row["window_id"] for row in features if row.get("window_id")})
    for window_id in windows:
        result = evaluate_window_coupling(
            scenario_id,
            window_id,
            features,
            threshold_z=float(policy.get("threshold_z", 1.5)),
            persistence_days=int(policy.get("persistence_days", 3)),
            run_permutation=False,
        )
        window_end = window_ends.get(window_id)
        for episode in result.episodes_k3:
            start = date.fromisoformat(episode.start_date)
            end = date.fromisoformat(episode.end_date)
            days_before_end = (window_end - end).days if window_end else 0
            episode_states = [
                state
                for state in result.daily_states
                if episode.start_date <= state.date <= episode.end_date
            ]
            unknowns = _unknowns(episode_states)
            imaging = {state.date: state.costly_status for state in episode_states}
            posture, reason = _recommended_posture(episode_states, policy)
            trigger = NoticeTrigger(
                scenario_id=scenario_id,
                window_id=window_id,
                collection_id=collection_id,
                measurement_id=measure_id,
                policy_id=str(policy["id"]),
                policy_params={
                    "threshold_z": float(policy.get("threshold_z", 1.5)),
                    "min_domains": int(policy.get("min_domains", 3)),
                    "persistence_days": int(policy.get("persistence_days", 3)),
                },
                created_at=created_at,
                start=start,
                end=end,
                duration_days=episode.duration_days,
                days_before_window_end=days_before_end,
                contributing_domains=list(episode.contributing_domains),
                contributing_series=list(episode.contributing_series),
                observed={
                    "daily_series_z": [state.series_z for state in episode_states],
                    "daily_dates": [state.date for state in episode_states],
                },
                derived={
                    "domain_energies": [state.domain_energies for state in episode_states],
                    "total_energy": [state.total_energy for state in episode_states],
                    "mean_energy": episode.mean_energy,
                    "max_energy": episode.max_energy,
                    "n_domains_z15": [state.n_domains_z15 for state in episode_states],
                },
                heuristic={
                    "policy_id": policy["id"],
                    "kind": policy.get("kind"),
                    "level": episode.level,
                    "tasking_order_days": episode.tasking_order_days,
                },
                unknowns=unknowns,
                imaging_status_by_day=imaging,
                recommended_posture=posture,
                recommended_posture_reason=reason,
            )
            ident = notice_id_for(trigger)
            path = notice_path(project_root, scenario_id, ident)
            if path.is_file():
                emitted.append(load_notice(project_root, scenario_id, ident))
                continue
            notice = Notice(notice_id=ident, trigger=trigger, workflow=NoticeWorkflow())
            save_notice(project_root, notice, overwrite_trigger=True)
            emitted.append(notice)
    return emitted


def _unknowns(states: list[DailyCouplingState]) -> list[str]:
    found: set[str] = set()
    for state in states:
        if state.costly_status == "unknown":
            found.add("imaging_unknown")
        for series_id, value in state.series_z.items():
            if value is None:
                found.add(series_id)
    return sorted(found)


def _recommended_posture(
    states: list[DailyCouplingState], policy: dict[str, Any]
) -> tuple[CollectionPosture, str]:
    imaging = {state.costly_status for state in states}
    default = CollectionPosture(policy.get("recommended_posture") or "focused")
    if "unknown" in imaging:
        return default, "chorus_with_imaging_gap"
    if "flagged" in imaging:
        return default, "chorus_with_physical_flag"
    return default, "chorus_with_physical_available"
