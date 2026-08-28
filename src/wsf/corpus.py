from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wsf.connectors import AOI_SOURCES, SOURCE_SERIES, default_connectors, extras_status
from wsf.connectors.base import (
    Connector,
    ConnectorResult,
    PullRequest,
    observation_payload,
    write_jsonl,
)
from wsf.connectors.daily import failed_result
from wsf.connectors.viirs import viirs_extra_available
from wsf.env import load_project_env
from wsf.progress import SILENT, Progress
from wsf.protocol import load_yaml
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
from wsf.time import date_range


def collect_corpus(
    project_root: Path,
    scenario_id: str,
    *,
    focus_path: Path | None = None,
    mock: bool = False,
    run_id: str | None = None,
    only: list[str] | None = None,
    connectors: dict[str, Connector] | None = None,
    progress: Progress | None = None,
) -> tuple[Path, dict[str, Any]]:
    scenario = load_scenario(project_root, scenario_id)
    require_collection_ready(scenario)
    log = progress or SILENT
    status = load_status(project_root, scenario_id)
    if status["phase"] == "frozen":
        raise ValueError("a frozen scenario cannot collect additional corpus data")

    selected = _selected_sources(scenario, only)
    focus = _load_focus(focus_path, scenario_id)
    collection_id = validate_run_id(run_id or new_run_id("collection"))
    directory = scenario_directory(project_root, scenario_id) / "corpus" / collection_id
    directory.mkdir(parents=True, exist_ok=False)
    windows = [scenario.incident, *scenario.controls]
    retrieved_at = datetime.now(UTC)

    log.line(
        f"collect {scenario_id} mode={'mock' if mock else 'live'} "
        f"sources={','.join(selected)} windows={len(windows)}"
    )
    if mock:
        items = _synthetic_items(scenario, windows, selected)
        mode = "synthetic_rehearsal"
        log.line(f"collect {scenario_id} mock items={len(items)}")
    else:
        load_project_env(project_root)
        _preflight_live(project_root, scenario, selected)
        registry = connectors or default_connectors(project_root)
        items = _live_items(
            project_root=project_root,
            scenario=scenario,
            scenario_id=scenario_id,
            windows=windows,
            selected=selected,
            focus=focus,
            parent_id=status.get("active_collection_id"),
            directory=directory,
            registry=registry,
            retrieved_at=retrieved_at,
            progress=log,
        )
        mode = "live_harvest"

    manifest = {
        "collection_id": collection_id,
        "scenario_id": scenario_id,
        "scenario_hash": scenario_hash(scenario),
        "created_at": retrieved_at.isoformat(),
        "mode": mode,
        "parent_collection_id": status.get("active_collection_id"),
        "focus_source": str(focus_path) if focus_path else None,
        "resolved_gap_ids": [item["gap_id"] for item in focus.get("critical_gaps", [])],
        "selected_sources": selected,
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
    log.line(f"collect {scenario_id} finished {collection_id} items={len(items)}")
    return directory, manifest


def _selected_sources(scenario: Any, only: list[str] | None) -> list[str]:
    enabled = [source for source, config in scenario.sources.items() if config.enabled]
    if not only:
        return enabled
    unknown = sorted(set(only) - set(scenario.sources))
    if unknown:
        raise ValueError(f"unknown sources: {', '.join(unknown)}")
    selected = [source for source in enabled if source in set(only)]
    if not selected:
        raise ValueError("no enabled sources remain after --only")
    return selected


def _preflight_live(project_root: Path, scenario: Any, selected: list[str]) -> None:
    if "alfred" in selected and scenario.queries.fred_series and not os.environ.get("FRED_API_KEY"):
        raise ValueError("FRED_API_KEY is required for live ALFRED collection")
    if "viirs" in selected:
        if not viirs_extra_available():
            raise ValueError(
                "live VIIRS requires `uv sync --extra viirs` and EARTHDATA_TOKEN; "
                "or collect with --only wikipedia,gdelt,alfred"
            )
        if not os.environ.get("EARTHDATA_TOKEN"):
            raise ValueError("EARTHDATA_TOKEN is required for live VIIRS collection")
        load_actor_aois(project_root, scenario.queries.facility_actor)


def _synthetic_items(
    scenario: Any, windows: list[Any], selected: list[str]
) -> list[dict[str, Any]]:
    items = []
    for source in selected:
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
                    "not_applicable": False,
                }
            )
    return items


def _live_items(
    *,
    project_root: Path,
    scenario: Any,
    scenario_id: str,
    windows: list[Any],
    selected: list[str],
    focus: dict[str, Any],
    parent_id: str | None,
    directory: Path,
    registry: dict[str, Connector],
    retrieved_at: datetime,
    progress: Progress,
) -> list[dict[str, Any]]:
    focus_pairs = {
        (item["source"], item["window_id"]) for item in focus.get("critical_gaps", [])
    }
    parent_items, parent_dir = _parent_live_items(project_root, scenario_id, parent_id)
    aois, timezone = ([], None)
    if AOI_SOURCES.intersection(selected):
        aois, timezone = load_actor_aois(project_root, scenario.queries.facility_actor)

    items: list[dict[str, Any]] = []
    jobs = [(source, window) for source in selected for window in windows]
    for job_index, (source, window) in enumerate(jobs, start=1):
        if source not in registry:
            raise ValueError(f"no connector registered for source {source}")
        prefix = f"collect {source}/{window.id} [{job_index}/{len(jobs)}]"
        key = (source, window.id)
        if focus_pairs and key not in focus_pairs and key in parent_items:
            progress.line(f"{prefix} copy from parent")
            items.append(_copy_parent_item(parent_dir, directory, parent_items[key]))
            continue
        progress.line(f"{prefix} start {window.start}..{window.end}")
        request = PullRequest(
            source=source,
            series_id=SOURCE_SERIES[source],
            scenario_id=scenario_id,
            window_id=window.id,
            start=window.start,
            end=window.end,
            queries=scenario.queries,
            aois=aois if source in AOI_SOURCES else [],
            timezone=timezone,
            retrieved_at=retrieved_at,
            output_dir=directory,
            progress=progress,
        )
        try:
            result = registry[source].pull(request)
        except Exception as error:  # noqa: BLE001
            progress.line(f"{prefix} error: {error}")
            result = failed_result(
                request, date_range(window.start, window.end), str(error), retrieved_at
            )
        items.append(_persist_result(directory, result))
        coverage = result.item.get("coverage")
        progress.line(f"{prefix} done coverage={coverage}")
    return items


def _persist_result(directory: Path, result: ConnectorResult) -> dict[str, Any]:
    item = result.item
    stem = f"{item['source']}_{item['window_id']}"
    observations_path = directory / "observations" / f"{stem}.jsonl"
    provenance_path = directory / "provenance" / f"{stem}.jsonl"
    checksum = write_jsonl(
        observations_path, [observation_payload(row) for row in result.observations]
    )
    write_jsonl(provenance_path, result.requests)
    item["checksum"] = checksum
    item["observations"] = str(observations_path.relative_to(directory))
    item["provenance"] = str(provenance_path.relative_to(directory))
    return item


def _parent_live_items(
    project_root: Path, scenario_id: str, parent_id: str | None
) -> tuple[dict[tuple[str, str], dict[str, Any]], Path | None]:
    if not parent_id:
        return {}, None
    parent_dir = scenario_directory(project_root, scenario_id) / "corpus" / parent_id
    manifest_path = parent_dir / "manifest.json"
    if not manifest_path.is_file():
        return {}, None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("mode") == "synthetic_rehearsal":
        return {}, None
    items = {(item["source"], item["window_id"]): item for item in manifest.get("items", [])}
    return items, parent_dir


def _copy_parent_item(
    parent_dir: Path | None, directory: Path, item: dict[str, Any]
) -> dict[str, Any]:
    copied = dict(item)
    copied["copied_from_parent"] = True
    if parent_dir is None:
        return copied
    for key in ("observations", "provenance"):
        relative = item.get(key)
        if not relative:
            continue
        source = parent_dir / relative
        dest = directory / relative
        if source.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
    return copied


def load_actor_aois(project_root: Path, actor: str) -> tuple[list[dict[str, Any]], str | None]:
    path = project_root / "config" / "facilities.yaml"
    if not path.is_file():
        raise ValueError(f"facilities.yaml is required for live VIIRS collection: missing {path}")
    data = load_yaml(path)
    entry = (data or {}).get("actors", {}).get(actor)
    if not entry:
        raise ValueError(f"no facilities configured for actor {actor}")
    aois = entry.get("aois") or []
    if len(aois) < 2:
        raise ValueError(f"{actor}: VIIRS requires at least two AOIs")
    return aois, entry.get("timezone")


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
    if manifest["mode"] == "synthetic_rehearsal":
        scientific = "rehearsal only"
    else:
        scientific = "live harvest; not yet a frozen scientific result"
    lines = [
        f"# Collection {manifest['collection_id']}",
        "",
        f"- Scenario: `{manifest['scenario_id']}`",
        f"- Mode: `{manifest['mode']}`",
        f"- Items: {len(manifest['items'])}",
        f"- Scientific status: {scientific}",
        "",
        "| Source | Window | Coverage | OK | Missing | Down | Notes |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for item in manifest["items"]:
        lines.append(
            f"| {item['source']} | {item['window_id']} | {item.get('coverage', 0):.3f} | "
            f"{item.get('n_ok', '-')} | {item.get('n_missing', '-')} | "
            f"{item.get('n_source_down', '-')} | {item.get('notes', '')} |"
        )
    return "\n".join(lines) + "\n"


def connector_readiness(project_root: Path) -> dict[str, Any]:
    env = load_project_env(project_root)
    return {**env, **extras_status()}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
