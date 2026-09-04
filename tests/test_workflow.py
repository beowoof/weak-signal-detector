from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from wsf.cli import app
from wsf.corpus import collect_corpus
from wsf.scenario import create_scenario, load_scenario, load_status
from wsf.workflow import run_desk_workflow

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _complete_scenario(project_root: Path, scenario_id: str = "ukraine2022") -> Path:
    if not (project_root / "config").exists():
        shutil.copytree(PROJECT_ROOT / "config", project_root / "config")
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


def test_from_after_through_is_rejected(tmp_path: Path) -> None:
    _complete_scenario(tmp_path)
    with pytest.raises(ValueError, match="after --through"):
        run_desk_workflow(
            tmp_path,
            "ukraine2022",
            from_stage="emit",
            through="collect",
            mock=True,
        )


def test_mock_workflow_stops_before_measure(tmp_path: Path) -> None:
    _complete_scenario(tmp_path)
    result = run_desk_workflow(tmp_path, "ukraine2022", mock=True)
    assert result["status"] == "stopped_mock"
    assert result["stages"] == ["validate", "collect", "review"]
    assert result["review"]["decision"] == "go_candidate_rehearsal"
    assert "measure" not in result
    assert "emit" not in result
    assert load_status(tmp_path, "ukraine2022")["phase"] == "reviewed"


def test_from_review_skips_collect(tmp_path: Path) -> None:
    _complete_scenario(tmp_path)
    first, _ = collect_corpus(tmp_path, "ukraine2022", mock=True)
    result = run_desk_workflow(
        tmp_path,
        "ukraine2022",
        from_stage="review",
        through="review",
        mock=True,
    )
    assert result["status"] == "completed"
    assert result["stages"] == ["validate", "review"]
    assert "collect" not in result
    assert load_status(tmp_path, "ukraine2022")["active_collection_id"] == first.name


def test_no_go_stops_and_names_focus_command(tmp_path: Path) -> None:
    _complete_scenario(tmp_path)
    collection_dir, _ = collect_corpus(
        tmp_path, "ukraine2022", mock=True, run_id="collection-original"
    )
    manifest_path = collection_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"][0]["provenance_complete"] = False
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result = run_desk_workflow(
        tmp_path,
        "ukraine2022",
        from_stage="review",
        mock=True,
    )
    assert result["status"] == "stopped_no_go"
    assert result["review"]["decision"] == "no_go"
    assert "measure" not in result
    assert "--focus" in result["next"]
    assert result["review"]["missing"] in result["next"]


def test_focus_without_collect_is_rejected(tmp_path: Path) -> None:
    _complete_scenario(tmp_path)
    with pytest.raises(ValueError, match="--focus requires the collect stage"):
        run_desk_workflow(
            tmp_path,
            "ukraine2022",
            from_stage="review",
            focus_path=tmp_path / "missing.json",
            mock=True,
        )


def test_cli_help_lists_workflow() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["run", "workflow", "--help"])
    assert result.exit_code == 0
    text = " ".join(result.stdout.split())
    assert "Validate, collect, review, measure" in text
    assert "--from" in result.stdout
    assert "--focus" in result.stdout


def test_cli_mock_workflow_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _complete_scenario(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "workflow", "--scenario", "ukraine2022", "--mock", "--quiet"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "stopped_mock"
    assert payload["scenario"] == "ukraine2022"
    load_scenario(tmp_path, "ukraine2022")


def test_cli_no_go_exits_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _complete_scenario(tmp_path)
    collection_dir, _ = collect_corpus(tmp_path, "ukraine2022", mock=True)
    manifest_path = collection_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"][0]["provenance_complete"] = False
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "workflow",
            "--scenario",
            "ukraine2022",
            "--from",
            "review",
            "--mock",
            "--quiet",
        ],
    )
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "stopped_no_go"
