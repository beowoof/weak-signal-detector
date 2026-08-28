from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wsf.run import new_run_id, validate_run_id
from wsf.scenario import (
    append_history,
    load_scenario,
    load_status,
    require_collection_ready,
    save_status,
    scenario_directory,
    scenario_hash,
)


def collect_corpus(
    project_root: Path,
    scenario_id: str,
    *,
    focus_path: Path | None = None,
    mock: bool = False,
    run_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    if not mock:
        raise NotImplementedError("live connectors are not implemented; use --mock for rehearsal")
    scenario = load_scenario(project_root, scenario_id)
    require_collection_ready(scenario)
    status = load_status(project_root, scenario_id)
    if status["phase"] == "frozen":
        raise ValueError("a frozen scenario cannot collect additional corpus data")

    focus = _load_focus(focus_path, scenario_id)
    collection_id = validate_run_id(run_id or new_run_id("collection"))
    directory = scenario_directory(project_root, scenario_id) / "corpus" / collection_id
    directory.mkdir(parents=True, exist_ok=False)
    windows = [scenario.incident, *scenario.controls]
    items = []
    for source, source_config in scenario.sources.items():
        if not source_config.enabled:
            continue
        for window in windows:
            items.append(
                {
                    "item_id": f"{source}:{window.id}",
                    "source": source,
                    "window_id": window.id,
                    "coverage": 1.0,
                    "provenance_complete": True,
                    "contains_post_cutoff_material": False,
                    "mode": "synthetic",
                    "checksum": f"mock-{source}-{window.id}",
                }
            )
    manifest = {
        "collection_id": collection_id,
        "scenario_id": scenario_id,
        "scenario_hash": scenario_hash(scenario),
        "created_at": datetime.now(UTC).isoformat(),
        "mode": "synthetic_rehearsal",
        "parent_collection_id": status.get("active_collection_id"),
        "focus_source": str(focus_path) if focus_path else None,
        "resolved_gap_ids": [item["gap_id"] for item in focus.get("critical_gaps", [])],
        "items": items,
    }
    _write_json(directory / "manifest.json", manifest)
    (directory / "collection_summary.md").write_text(
        _collection_markdown(manifest), encoding="utf-8"
    )
    status.update(
        {
            "phase": "collected",
            "active_collection_id": collection_id,
            "active_review_id": None,
        }
    )
    save_status(project_root, scenario_id, status)
    append_history(
        scenario_directory(project_root, scenario_id),
        "corpus_collected",
        {"collection_id": collection_id, "mode": manifest["mode"]},
    )
    return directory, manifest


def _load_focus(path: Path | None, scenario_id: str) -> dict[str, Any]:
    if path is None:
        return {"critical_gaps": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value.get("critical_gaps"), list):
        raise ValueError("focus file must contain critical_gaps list")
    if value.get("scenario_id") != scenario_id:
        raise ValueError("focus file belongs to a different scenario")
    if value.get("decision") != "no_go":
        raise ValueError("focus file must come from a NO-GO review")
    return value


def _collection_markdown(manifest: dict[str, Any]) -> str:
    return (
        f"# Collection {manifest['collection_id']}\n\n"
        f"- Scenario: `{manifest['scenario_id']}`\n"
        f"- Mode: `{manifest['mode']}`\n"
        f"- Items: {len(manifest['items'])}\n"
        "- Scientific status: rehearsal only\n"
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
