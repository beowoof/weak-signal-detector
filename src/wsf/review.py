from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wsf.progress import SILENT, Progress
from wsf.run import new_run_id, validate_run_id
from wsf.scenario import (
    append_history,
    load_scenario,
    load_status,
    save_status,
    scenario_directory,
    scenario_hash,
)


def review_corpus(
    project_root: Path,
    scenario_id: str,
    *,
    mock_model: bool = False,
    run_id: str | None = None,
    progress: Progress | None = None,
) -> tuple[Path, dict[str, Any]]:
    log = progress or SILENT
    log.line(f"review {scenario_id} start")
    scenario = load_scenario(project_root, scenario_id)
    status = load_status(project_root, scenario_id)
    if status["phase"] == "frozen":
        raise ValueError("a frozen scenario cannot be reviewed again")
    collection_id = status.get("active_collection_id")
    if not collection_id:
        raise ValueError("scenario has no active corpus collection")
    scenario_dir = scenario_directory(project_root, scenario_id)
    collection_path = scenario_dir / "corpus" / collection_id / "manifest.json"
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    if collection.get("scenario_hash") != scenario_hash(scenario):
        raise ValueError("scenario changed after collection; collect a new corpus revision")

    review_id = validate_run_id(run_id or new_run_id("review"))
    directory = scenario_dir / "reviews" / review_id
    directory.mkdir(parents=True, exist_ok=False)
    log.line(f"review {scenario_id} collection={collection_id} deterministic gates")
    gaps = _deterministic_gaps(scenario, collection)
    critical = [item for item in gaps if item["severity"] == "critical"]
    warnings = [item for item in gaps if item["severity"] != "critical"]
    deterministic = {
        "review_id": review_id,
        "scenario_id": scenario_id,
        "collection_id": collection_id,
        "created_at": datetime.now(UTC).isoformat(),
        "hard_gate_pass": not critical,
        "gaps": gaps,
        "critical_gaps": critical,
        "warning_gaps": warnings,
    }
    _write_json(directory / "deterministic_review.json", deterministic)

    queue_item = {
        "task_id": f"{review_id}:semantic-balance",
        "task": "review_corpus_balance",
        "model": scenario.interpretation.model,
        "corpus_manifest": str(collection_path),
        "instructions": [
            "Assess incident/control symmetry and source diversity.",
            "Find query terms that encode the known outcome.",
            "Identify missing alternatives or counterevidence.",
            "Cite corpus item ids for every finding.",
            "Do not infer missing observations or use the eventual outcome as evidence.",
        ],
    }
    _write_jsonl(directory / "model_queue.jsonl", [queue_item])

    if critical:
        decision = "no_go"
        semantic = {"status": "not_run_due_to_hard_gate", "critical_gaps": critical}
    elif mock_model:
        decision = "go_candidate_rehearsal"
        semantic = {
            "status": "mocked",
            "critical_gaps": [],
            "grounding_rate": 1.0,
            "notes": "Synthetic response for engineering workflow tests only.",
        }
        _write_jsonl(directory / "model_responses.jsonl", [semantic])
    else:
        decision = "model_pending"
        semantic = {"status": "pending_operator_model_run", "critical_gaps": []}

    missing = {
        "review_id": review_id,
        "scenario_id": scenario_id,
        "collection_id": collection_id,
        "decision": decision,
        "critical_gaps": critical,
        "warning_gaps": warnings,
    }
    result = {
        "review_id": review_id,
        "scenario_id": scenario_id,
        "scenario_hash": scenario_hash(scenario),
        "collection_id": collection_id,
        "decision": decision,
        "deterministic": deterministic,
        "semantic": semantic,
    }
    _write_json(directory / "missing.json", missing)
    _write_json(directory / "decision.json", result)
    (directory / "review.md").write_text(_review_markdown(result), encoding="utf-8")

    status.update({"phase": "reviewed", "active_review_id": review_id})
    save_status(project_root, scenario_id, status)
    append_history(
        scenario_dir,
        "corpus_reviewed",
        {"review_id": review_id, "collection_id": collection_id, "decision": decision},
    )
    log.line(
        f"review {scenario_id} {review_id} decision={decision} "
        f"critical={len(critical)} warnings={len(warnings)}"
    )
    return directory, result


def _deterministic_gaps(scenario: Any, collection: dict[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    selected = set(collection.get("selected_sources") or [])
    for source, config in scenario.sources.items():
        if (
            config.enabled
            and source not in selected
            and source not in {item["source"] for item in collection["items"]}
        ):
            gaps.append(
                _gap(
                    "missing_source",
                    source,
                    "all",
                    f"enabled source {source} was not collected",
                    "collect_enabled_source",
                )
            )
    for item in collection["items"]:
        by_source[item["source"]].append(item)
        if item.get("not_applicable"):
            continue
        n_expected = item.get("n_expected") or 0
        n_down = item.get("n_source_down") or 0
        if n_expected and n_down >= n_expected:
            gaps.append(
                _gap(
                    "source_unavailable",
                    item["source"],
                    item["window_id"],
                    f"{item['source']} returned source_down for every expected day",
                    "repair_connector_or_credentials",
                )
            )
        threshold = (
            scenario.corpus_gates.minimum_valid_viirs_fraction
            if item["source"] == "viirs"
            else scenario.corpus_gates.minimum_daily_coverage
        )
        if item["coverage"] < threshold:
            weather_limited = item["source"] == "viirs"
            gaps.append(
                _gap(
                    "coverage_below_threshold",
                    item["source"],
                    item["window_id"],
                    f"coverage {item['coverage']:.3f} is below {threshold:.3f}; "
                    + (
                        "weather-limited nights remain unknown"
                        if weather_limited
                        else "the declared daily coverage gate failed"
                    ),
                    "continue_with_recorded_weather_gaps"
                    if weather_limited
                    else "repair_or_recollect_source",
                    severity="warning" if weather_limited else "critical",
                )
            )
        if scenario.corpus_gates.require_complete_provenance and not item["provenance_complete"]:
            gaps.append(
                _gap(
                    "incomplete_provenance",
                    item["source"],
                    item["window_id"],
                    "source item lacks complete provenance",
                    "recollect_with_provenance",
                )
            )
        if (
            scenario.corpus_gates.forbid_post_cutoff_material
            and item["contains_post_cutoff_material"]
        ):
            gaps.append(
                _gap(
                    "post_cutoff_material",
                    item["source"],
                    item["window_id"],
                    "source item contains post-cutoff material",
                    "replace_with_cutoff_safe_source",
                )
            )

    control_ids = {item.id for item in scenario.controls}
    for source, items in by_source.items():
        incident = next((item for item in items if item["window_id"] == scenario.incident.id), None)
        controls = [item for item in items if item["window_id"] in control_ids]
        if incident:
            for control in controls:
                difference = abs(incident["coverage"] - control["coverage"])
                maximum = scenario.corpus_gates.maximum_incident_control_coverage_difference
                if difference > maximum:
                    gaps.append(
                        _gap(
                            "incident_control_coverage_imbalance",
                            source,
                            control["window_id"],
                            f"coverage differs from incident by {difference:.3f} "
                            f"(> {maximum:.3f}); recorded, not blocking",
                            "continue_with_available_sources",
                            severity="warning",
                        )
                    )

    query_text = " ".join(scenario.queries.wiki_titles).lower()
    for term in scenario.corpus_gates.forbidden_outcome_terms:
        if term.lower() in query_text:
            gaps.append(
                _gap(
                    "outcome_encoded_query",
                    "wikipedia",
                    "all",
                    f"query contains forbidden outcome term: {term}",
                    "replace_query_with_cutoff_safe_title",
                )
            )
    return gaps


def _gap(
    gap_type: str,
    source: str,
    window_id: str,
    reason: str,
    requested_action: str,
    *,
    severity: str = "critical",
) -> dict[str, Any]:
    return {
        "gap_id": f"{gap_type}:{source}:{window_id}",
        "severity": severity,
        "source": source,
        "window_id": window_id,
        "reason": reason,
        "requested_action": requested_action,
    }


def _review_markdown(result: dict[str, Any]) -> str:
    deterministic = result["deterministic"]
    critical = deterministic.get("critical_gaps") or []
    warnings = deterministic.get("warning_gaps") or []
    return (
        f"# Corpus review {result['review_id']}\n\n"
        f"- Scenario: `{result['scenario_id']}`\n"
        f"- Collection: `{result['collection_id']}`\n"
        f"- Decision: **{result['decision']}**\n\n"
        f"## Critical gaps\n\n{_bullet(critical)}\n\n"
        f"## Warnings (missingness is not a stop)\n\n{_bullet(warnings)}\n"
    )


def _bullet(gaps: list[dict[str, Any]]) -> str:
    if not gaps:
        return "- None"
    return "\n".join(f"- {item['gap_id']}: {item['reason']}" for item in gaps)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True) + "\n")
