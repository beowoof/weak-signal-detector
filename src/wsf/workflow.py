"""Operator pipeline: validate → collect → review → measure → emit."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wsf.corpus import collect_corpus
from wsf.measure import measure_scenario
from wsf.notice import emit_notices_for_measurement
from wsf.progress import SILENT, Progress
from wsf.review import review_corpus
from wsf.scenario import (
    load_scenario,
    load_status,
    prepare_scenario_workspace,
    require_collection_ready,
    scenario_directory,
    scenario_hash,
)

STAGES = ("validate", "collect", "review", "measure", "emit")


def run_desk_workflow(
    project_root: Path,
    scenario_id: str,
    *,
    from_stage: str = "validate",
    through: str = "emit",
    focus_path: Path | None = None,
    mock: bool = False,
    exploratory: bool = True,
    only: list[str] | None = None,
    source_workers: int = 4,
    progress: Progress | None = None,
    checkpoint=None,
    should_stop=None,
) -> dict[str, Any]:
    """Run the sitting-desk pipeline. Does not freeze, prune, call Ollama, or build packets."""
    start = _stage_index(from_stage, "--from")
    end = _stage_index(through, "--through")
    if start > end:
        raise ValueError(f"--from {from_stage} is after --through {through}")
    if focus_path is not None and not _wanted("collect", start, end):
        raise ValueError("--focus requires the collect stage; omit --from review or later")

    log = progress or SILENT
    summary: dict[str, Any] = {
        "scenario": scenario_id,
        "from": from_stage,
        "through": through,
        "mock": mock,
        "started_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "stages": [],
    }
    log.line(f"workflow {scenario_id} from={from_stage} through={through}")

    def continuing():
        if checkpoint:
            checkpoint(summary)
        if should_stop and should_stop():
            summary["status"] = "stopped_by_user"
            return False
        return True

    try:
        _validate(project_root, scenario_id, summary)
        if not continuing():
            return summary
        if _wanted("collect", start, end):
            _collect(
                project_root,
                scenario_id,
                summary,
                focus_path=focus_path,
                mock=mock,
                only=only,
                source_workers=source_workers,
                progress=log,
            )
        if not continuing():
            return summary
        if _wanted("review", start, end):
            decision = _review(project_root, scenario_id, summary, mock=mock, progress=log)
            if decision == "no_go":
                missing = Path(summary["review"]["missing"])
                summary["status"] = "stopped_no_go"
                summary["next"] = f"wsd run workflow --scenario {scenario_id} --focus {missing}"
                log.line(
                    f"workflow {scenario_id} stopped: review is no_go. "
                    f"Fix and re-run with --focus {missing}"
                )
                return summary
        if not continuing():
            return summary
        if _wanted("measure", start, end):
            if mock:
                summary["status"] = "stopped_mock"
                summary["next"] = None
                log.line(
                    f"workflow {scenario_id} stopped after review: mock harvests cannot be measured"
                )
                return summary
            decision = _active_review_decision(project_root, scenario_id)
            if decision == "no_go":
                status = load_status(project_root, scenario_id)
                review_id = status.get("active_review_id")
                missing = (
                    scenario_directory(project_root, scenario_id)
                    / "reviews"
                    / str(review_id)
                    / "missing.json"
                )
                summary["status"] = "stopped_no_go"
                summary["next"] = f"wsd run workflow --scenario {scenario_id} --focus {missing}"
                log.line(
                    f"workflow {scenario_id} stopped: active review is no_go. "
                    f"Re-run with --focus {missing}"
                )
                return summary
            _measure(
                project_root,
                scenario_id,
                summary,
                exploratory=exploratory,
                progress=log,
            )
        if not continuing():
            return summary
        if _wanted("emit", start, end):
            _emit(project_root, scenario_id, summary)
        summary["status"] = "completed"
        summary["next"] = _next_after_emit(scenario_id, summary)
        log.line(f"workflow {scenario_id} finished status={summary['status']}")
        return summary
    finally:
        summary["finished_at"] = datetime.now(UTC).isoformat()
        if checkpoint:
            checkpoint(summary)


def _stage_index(name: str, flag: str) -> int:
    if name not in STAGES:
        raise ValueError(f"{flag} must be one of {', '.join(STAGES)}")
    return STAGES.index(name)


def _wanted(stage: str, start: int, end: int) -> bool:
    index = STAGES.index(stage)
    return start <= index <= end


def _validate(project_root: Path, scenario_id: str, summary: dict[str, Any]) -> None:
    prepare_scenario_workspace(project_root, scenario_id)
    scenario = load_scenario(project_root, scenario_id)
    require_collection_ready(scenario)
    payload = {
        "stage": "validate",
        "collection_ready": True,
        "scenario_hash": scenario_hash(scenario),
    }
    summary["validate"] = payload
    summary["stages"].append("validate")


def _collect(
    project_root: Path,
    scenario_id: str,
    summary: dict[str, Any],
    *,
    focus_path: Path | None,
    mock: bool,
    only: list[str] | None,
    source_workers: int,
    progress: Progress,
) -> None:
    directory, manifest = collect_corpus(
        project_root,
        scenario_id,
        focus_path=focus_path,
        mock=mock,
        only=only,
        progress=progress,
        source_workers=source_workers,
    )
    payload = {
        "stage": "collect",
        "collection_id": manifest["collection_id"],
        "directory": str(directory),
        "mode": manifest["mode"],
    }
    summary["collect"] = payload
    summary["stages"].append("collect")


def _review(
    project_root: Path,
    scenario_id: str,
    summary: dict[str, Any],
    *,
    mock: bool,
    progress: Progress,
) -> str:
    directory, result = review_corpus(
        project_root,
        scenario_id,
        mock_model=mock,
        progress=progress,
    )
    payload = {
        "stage": "review",
        "review_id": result["review_id"],
        "decision": result["decision"],
        "directory": str(directory),
        "missing": str(directory / "missing.json"),
    }
    summary["review"] = payload
    summary["stages"].append("review")
    return str(result["decision"])


def _measure(
    project_root: Path,
    scenario_id: str,
    summary: dict[str, Any],
    *,
    exploratory: bool,
    progress: Progress,
) -> None:
    directory, result = measure_scenario(
        project_root,
        scenario_id,
        exploratory=exploratory,
        progress=progress,
    )
    payload = {
        "stage": "measure",
        "measure_id": result["measure_id"],
        "directory": str(directory),
        "measurement_mode": result["measurement_mode"],
        "scientific_result": result["scientific_result"],
        "protocol_alerts": len(result["protocol_alerts"]),
        "exploratory_alerts": len(result["exploratory_alerts"]),
        "rhythm_alerts": len(result.get("rhythm_alerts") or []),
        "amber_alerts": len(result.get("amber_alerts") or []),
    }
    summary["measure"] = payload
    summary["stages"].append("measure")


def _emit(project_root: Path, scenario_id: str, summary: dict[str, Any]) -> None:
    notices = emit_notices_for_measurement(project_root, scenario_id)
    payload = {
        "stage": "emit",
        "n_notices": len(notices),
        "notices": [
            {
                "notice_id": item.notice_id,
                "window_id": item.trigger.window_id,
                "start": item.trigger.start.isoformat(),
                "end": item.trigger.end.isoformat(),
                "days_before_window_end": item.trigger.days_before_window_end,
                "domains": item.trigger.contributing_domains,
                "posture": item.trigger.recommended_posture.value,
                "state": item.workflow.state.value,
            }
            for item in notices
        ],
    }
    summary["emit"] = payload
    summary["stages"].append("emit")


def _next_after_emit(scenario_id: str, summary: dict[str, Any]) -> list[str] | None:
    notices = (summary.get("emit") or {}).get("notices") or []
    if not notices:
        return None
    return [
        f"wsd packet build --scenario {scenario_id} --notice {item['notice_id']} --replay"
        for item in notices
    ]


def _active_review_decision(project_root: Path, scenario_id: str) -> str | None:
    status = load_status(project_root, scenario_id)
    review_id = status.get("active_review_id")
    if not review_id:
        return None
    path = scenario_directory(project_root, scenario_id) / "reviews" / review_id / "decision.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("decision")
