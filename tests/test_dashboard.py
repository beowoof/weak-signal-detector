import json
from pathlib import Path

import pytest

from dashboard.server import discover_results, load_result, result_index


def write_result(root: Path, scenario_id: str, measure_id: str) -> None:
    scenario_dir = root / scenario_id
    result_dir = scenario_dir / "measurement" / measure_id
    result_dir.mkdir(parents=True)
    (scenario_dir / "scenario.json").write_text(
        json.dumps(
            {
                "scenario_id": scenario_id,
                "purpose": "test",
                "incident": {"id": "incident", "start": "2020-01-01", "end": "2020-01-02"},
            }
        ),
        encoding="utf-8",
    )
    (result_dir / "summary.json").write_text(
        json.dumps(
            {
                "measure_id": measure_id,
                "n_feature_rows": 1,
                "protocol_id": "coincidence_test",
            }
        ),
        encoding="utf-8",
    )
    (result_dir / "features.jsonl").write_text(
        json.dumps(
            {
                "event_day": "2020-01-01",
                "series_id": "test.series",
                "window_id": "incident",
                "raw": 3.0,
                "z": 1.5,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (result_dir / "days.jsonl").write_text(
        json.dumps({"day": "2020-01-01", "window_id": "incident", "verdict": "quiet"})
        + "\n",
        encoding="utf-8",
    )


def test_discover_index_and_load_result(tmp_path: Path) -> None:
    write_result(tmp_path, "scenario-a", "measure-002")
    write_result(tmp_path, "scenario-a", "measure-001")

    refs = discover_results(tmp_path)
    assert [item.key for item in refs] == [
        "scenario-a/measure-002",
        "scenario-a/measure-001",
    ]

    index = result_index(tmp_path)
    assert len(index["results"]) == 2
    assert index["results"][0]["measurement_mode"] == "legacy_unspecified"
    assert index["scenarios"]["scenario-a"]["purpose"] == "test"

    result = load_result("scenario-a/measure-002", tmp_path)
    assert result["summary"]["protocol_id"] == "coincidence_test"
    assert result["features"][0]["z"] == 1.5
    assert result["days"][0]["verdict"] == "quiet"
    assert "coupling" in result


def test_load_result_rejects_unknown_key(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        load_result("../../outside", tmp_path)
