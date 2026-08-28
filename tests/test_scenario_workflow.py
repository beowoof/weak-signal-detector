from __future__ import annotations

import json
from pathlib import Path

import pytest

from run_test import run_experiment
from wsf.corpus import collect_corpus
from wsf.review import review_corpus
from wsf.scenario import (
    create_scenario,
    freeze_scenario,
    load_scenario,
    load_status,
    require_collection_ready,
)


def _complete_scenario(project_root: Path, scenario_id: str = "ukraine2022") -> Path:
    directory = create_scenario(project_root, scenario_id)
    path = directory / "scenario.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["actors"] = {"focal": "RUS", "counterparts": ["UKR"]}
    value["incident"].update(
        {
            "start": "2022-02-17",
            "end": "2022-02-23",
            "target_start": "2022-02-24",
            "target_end": "2022-03-02",
            "selection_reason": "Seven days immediately before the declared target event.",
        }
    )
    value["controls"][0].update(
        {
            "start": "2021-02-18",
            "end": "2021-02-24",
            "target_start": None,
            "target_end": None,
            "selection_reason": "Same seasonal week in the prior year without the target event.",
        }
    )
    value["queries"].update(
        {
            "wiki_titles": ["Russia", "Ukraine", "Russian Armed Forces"],
            "cameo_actor": "RUS",
            "facility_actor": "RUS",
        }
    )
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return directory


def test_created_scenario_is_deliberately_incomplete(tmp_path: Path) -> None:
    directory = create_scenario(tmp_path, "example-case")

    with pytest.raises(ValueError, match="actors.focal"):
        require_collection_ready(load_scenario(tmp_path, "example-case"))
    assert load_status(tmp_path, "example-case")["phase"] == "draft"
    assert (directory / "history.jsonl").is_file()


def test_mock_workflow_can_be_rehearsed_but_not_frozen_as_real(tmp_path: Path) -> None:
    _complete_scenario(tmp_path)
    collection_dir, _ = collect_corpus(tmp_path, "ukraine2022", mock=True)
    review_dir, review = review_corpus(tmp_path, "ukraine2022", mock_model=True)

    assert (collection_dir / "manifest.json").is_file()
    assert (review_dir / "model_queue.jsonl").is_file()
    assert review["decision"] == "go_candidate_rehearsal"
    with pytest.raises(ValueError, match="cannot be frozen"):
        freeze_scenario(tmp_path, "ukraine2022")

    freeze = freeze_scenario(tmp_path, "ukraine2022", allow_rehearsal=True)
    assert json.loads(freeze.read_text(encoding="utf-8"))["rehearsal"] is True
    assert load_status(tmp_path, "ukraine2022")["phase"] == "frozen"


def test_no_go_missing_file_can_drive_focused_recollection(tmp_path: Path) -> None:
    scenario_dir = _complete_scenario(tmp_path)
    collection_dir, _ = collect_corpus(
        tmp_path, "ukraine2022", mock=True, run_id="collection-original"
    )
    manifest_path = collection_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"][0]["provenance_complete"] = False
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    review_dir, review = review_corpus(
        tmp_path, "ukraine2022", mock_model=True, run_id="review-no-go"
    )
    missing_path = review_dir / "missing.json"
    missing = json.loads(missing_path.read_text(encoding="utf-8"))
    assert review["decision"] == "no_go"
    assert missing["critical_gaps"]

    _, focused = collect_corpus(
        tmp_path,
        "ukraine2022",
        focus_path=missing_path,
        mock=True,
        run_id="collection-focused",
    )
    assert focused["parent_collection_id"] == "collection-original"
    assert focused["resolved_gap_ids"] == [item["gap_id"] for item in missing["critical_gaps"]]
    _, second_review = review_corpus(
        tmp_path, "ukraine2022", mock_model=True, run_id="review-after-focus"
    )
    assert second_review["decision"] == "go_candidate_rehearsal"
    history = (scenario_dir / "history.jsonl").read_text(encoding="utf-8")
    assert history.count("corpus_collected") == 2


def test_coverage_holes_are_warnings_not_no_go(tmp_path: Path) -> None:
    _complete_scenario(tmp_path)
    collection_dir, _ = collect_corpus(tmp_path, "ukraine2022", mock=True)
    manifest_path = collection_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["items"]:
        if item["source"] == "viirs":
            item["coverage"] = 0.25
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    _, review = review_corpus(tmp_path, "ukraine2022", mock_model=True)
    assert review["decision"] == "go_candidate_rehearsal"
    warnings = review["deterministic"]["warning_gaps"]
    assert any(item["gap_id"].startswith("coverage_below_threshold:viirs") for item in warnings)
    assert review["deterministic"]["critical_gaps"] == []


def test_review_refuses_scenario_changed_after_collection(tmp_path: Path) -> None:
    directory = _complete_scenario(tmp_path)
    collect_corpus(tmp_path, "ukraine2022", mock=True)
    path = directory / "scenario.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["research_question"] = "A changed question"
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after collection"):
        review_corpus(tmp_path, "ukraine2022", mock_model=True)


def test_freeze_refuses_scenario_changed_after_review(tmp_path: Path) -> None:
    directory = _complete_scenario(tmp_path)
    collect_corpus(tmp_path, "ukraine2022", mock=True)
    review_corpus(tmp_path, "ukraine2022", mock_model=True)
    path = directory / "scenario.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["research_question"] = "A changed question after review"
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after review"):
        freeze_scenario(tmp_path, "ukraine2022", allow_rehearsal=True)


def test_experiment_harness_records_one_parent_run(tmp_path: Path) -> None:
    _complete_scenario(tmp_path)
    run_dir, summary = run_experiment(
        scenario_id="ukraine2022",
        through="review",
        run_id="experiment-example",
        mock=True,
        project_root=tmp_path,
    )

    assert summary["status"] == "completed"
    assert summary["scientific_result"] is False
    assert summary["review"]["decision"] == "go_candidate_rehearsal"
    assert (run_dir / "experiment_summary.json").is_file()
    assert (run_dir / "experiment_summary.md").is_file()
