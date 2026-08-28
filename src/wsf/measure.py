from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from wsf.features.coincidence import FlaggedSeries, alerts_from_basket_days, basket_day
from wsf.features.cutoff import select_expected_row
from wsf.features.zscore import build_feature
from wsf.progress import SILENT, Progress
from wsf.protocol import load_yaml
from wsf.run import new_run_id, validate_run_id
from wsf.scenario import (
    append_history,
    load_scenario,
    load_status,
    save_status,
    scenario_directory,
    scenario_hash,
)
from wsf.time import date_range
from wsf.types import CausalDomain, CostClass, IndicatorSpec, Observation, Polarity

EXPLORATORY_N_MIN = 7
SOURCE_LAG = {
    "wikipedia": 1,
    "wiki_edits": 0,
    "gdelt": 0,
    "viirs": 3,
    "alfred": 0,
    "moex": 0,
    "firms": 0,
    "osm": 0,
    "ripe": 0,
    "official": 1,
    "ct": 0,
    "icews": 0,
    "brent": 0,
    "sar": 1,
}


def measure_scenario(
    project_root: Path,
    scenario_id: str,
    *,
    run_id: str | None = None,
    progress: Progress | None = None,
) -> tuple[Path, dict[str, Any]]:
    log = progress or SILENT
    scenario = load_scenario(project_root, scenario_id)
    status = load_status(project_root, scenario_id)
    collection_id = status.get("active_collection_id")
    if not collection_id:
        raise ValueError("scenario has no active corpus collection")
    scenario_dir = scenario_directory(project_root, scenario_id)
    collection_dir = scenario_dir / "corpus" / collection_id
    manifest = json.loads((collection_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("scenario_hash") != scenario_hash(scenario):
        raise ValueError("scenario changed after collection; collect a new corpus revision")
    if manifest.get("mode") == "synthetic_rehearsal":
        raise ValueError("measurement requires a live harvest, not a synthetic rehearsal")

    protocol = load_yaml(project_root / "config" / "protocol.yaml")
    indicators = TypeAdapter(list[IndicatorSpec]).validate_python(
        load_yaml(project_root / "config" / "indicator_register.yaml")
    )
    skipped = {
        item.get("series_id")
        for item in manifest.get("items", [])
        if item.get("not_applicable")
    }
    basket = [
        item
        for item in indicators
        if item.in_basket
        and item.connector
        and (item.series_id or item.id) not in skipped
    ]
    observations = _load_observations(collection_dir, manifest)
    windows = [scenario.incident, *scenario.controls]
    measure_id = validate_run_id(run_id or new_run_id("measure"))
    out_dir = scenario_dir / "measurement" / measure_id
    out_dir.mkdir(parents=True, exist_ok=False)
    log.line(f"measure {scenario_id} collection={collection_id} series={len(basket)}")

    rows: list[dict[str, Any]] = []
    day_verdicts: list[dict[str, Any]] = []
    protocol_flags: list[FlaggedSeries] = []
    exploratory_flags: list[FlaggedSeries] = []

    for window in windows:
        assert window.start is not None and window.end is not None
        days = date_range(window.start, window.end)
        for day in days:
            states: dict[str, str] = {}
            details: dict[str, dict[str, Any]] = {}
            for indicator in basket:
                scored = _score_series(
                    observations,
                    indicator=indicator,
                    window_id=window.id,
                    event_day=day,
                    protocol=protocol,
                )
                rows.append(scored)
                states[indicator.series_id or indicator.id] = scored["state"]
                details[indicator.series_id or indicator.id] = scored
                flag = _as_flag(indicator, window.id, day, scored)
                if flag and scored["protocol_eligible"]:
                    protocol_flags.append(flag)
                if flag:
                    exploratory_flags.append(flag)
            verdict = _day_verdict(states, basket)
            day_verdicts.append(
                {
                    "window_id": window.id,
                    "day": day.isoformat(),
                    "states": states,
                    "verdict": verdict,
                }
            )
            log.status(f"measure {window.id} {day.isoformat()} {verdict}")

    protocol_alerts = _alerts_for(protocol_flags, protocol)
    exploratory_alerts = _alerts_for(exploratory_flags, protocol)
    summary = {
        "measure_id": measure_id,
        "scenario_id": scenario_id,
        "collection_id": collection_id,
        "scenario_hash": scenario_hash(scenario),
        "protocol_id": protocol.get("protocol_id"),
        "exploratory_n_min": EXPLORATORY_N_MIN,
        "protocol_n_min": protocol.get("n_min"),
        "scientific_result": False,
        "notes": [
            "A missing or cloudy observation is unknown threat, not normal activity.",
            "Exploratory z-scores use available in-window history; they are not coincidence_v0.",
            "Protocol flags require n_baseline >= protocol n_min.",
            "Coincidence is across causal domains, not merely source families.",
        ],
        "n_feature_rows": len(rows),
        "protocol_alerts": [item.model_dump(mode="json") for item in protocol_alerts],
        "exploratory_alerts": [item.model_dump(mode="json") for item in exploratory_alerts],
        "verdict_counts": _count_verdicts(day_verdicts),
    }
    _write_json(out_dir / "summary.json", summary)
    _write_jsonl(out_dir / "features.jsonl", rows)
    _write_jsonl(out_dir / "days.jsonl", day_verdicts)
    (out_dir / "measurement.md").write_text(
        _markdown(summary, day_verdicts, basket), encoding="utf-8"
    )
    status.update({"phase": "measured", "active_measurement_id": measure_id})
    save_status(project_root, scenario_id, status)
    append_history(
        scenario_dir,
        "scenario_measured",
        {"measure_id": measure_id, "collection_id": collection_id},
    )
    log.line(
        f"measure {scenario_id} finished {measure_id} "
        f"protocol_alerts={len(protocol_alerts)} exploratory_alerts={len(exploratory_alerts)}"
    )
    return out_dir, summary


def _score_series(
    observations: list[Observation],
    *,
    indicator: IndicatorSpec,
    window_id: str,
    event_day: date,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    series_id = indicator.series_id or indicator.id
    lag = SOURCE_LAG.get(indicator.connector or "", 0)
    cutoff_day = event_day + timedelta(days=lag)
    relevant = [
        item
        for item in observations
        if item.period_id == window_id and item.series_id == series_id
    ]
    observed = select_expected_row(relevant, cutoff_day, expected_lag_days=lag)
    payload = {
        "window_id": window_id,
        "series_id": series_id,
        "source": indicator.connector,
        "family": indicator.family.value,
        "causal_domain": indicator.causal_domain.value if indicator.causal_domain else None,
        "cost_class": indicator.cost_class.value,
        "event_day": event_day.isoformat(),
        "cutoff": cutoff_day.isoformat(),
        "protocol_eligible": False,
        "z": None,
        "n_baseline": 0,
        "raw": None,
        "quality": None,
    }
    if observed is None:
        payload.update(
            {
                "state": "unknown",
                "unknown_reason": "absent",
                "threat": "unknown",
            }
        )
        return payload
    payload["quality"] = observed.quality
    payload["raw"] = observed.value
    if observed.quality != "ok" or observed.value is None:
        payload.update(
            {
                "state": "unknown",
                "unknown_reason": observed.quality,
                "threat": "unknown",
            }
        )
        return payload

    feature = build_feature(
        relevant,
        period_id=window_id,
        series_id=series_id,
        cutoff_day=cutoff_day,
        expected_lag_days=lag,
        window_days=int(protocol.get("window_days", 90)),
        n_min=EXPLORATORY_N_MIN,
        threshold=float(protocol.get("z_threshold", 2.5)),
        polarity=indicator.polarity or Polarity.high_unusual,
    )
    payload["z"] = feature.z
    payload["n_baseline"] = feature.n_baseline
    payload["protocol_eligible"] = (
        not feature.missing and feature.n_baseline >= int(protocol.get("n_min", 20))
    )
    if feature.missing:
        payload.update(
            {
                "state": "insufficient_baseline",
                "unknown_reason": "n_baseline_below_exploratory_min",
                "threat": "unknown",
            }
        )
        return payload
    if feature.flagged:
        payload.update({"state": "flagged", "threat": "elevated"})
        return payload
    payload.update({"state": "normal", "threat": "not_elevated"})
    return payload


def _as_flag(
    indicator: IndicatorSpec, window_id: str, day: date, scored: dict[str, Any]
) -> FlaggedSeries | None:
    if scored["state"] != "flagged":
        return None
    return FlaggedSeries(
        period_id=window_id,
        day=day,
        series_id=indicator.series_id or indicator.id,
        family=indicator.family,
        source_system=indicator.source_system or indicator.connector or "unknown",
        cost_class=indicator.cost_class,
        causal_domain=indicator.causal_domain or CausalDomain.information,
    )


def _day_verdict(states: dict[str, str], basket: list[IndicatorSpec]) -> str:
    costly_ids = [
        item.series_id or item.id for item in basket if item.cost_class is CostClass.costly
    ]
    flagged = {key for key, state in states.items() if state == "flagged"}
    unknown = {
        key for key, state in states.items() if state in {"unknown", "insufficient_baseline"}
    }
    domains = {
        item.causal_domain
        for item in basket
        if (item.series_id or item.id) in flagged and item.causal_domain is not None
    }
    sources = {
        item.source_system or item.connector
        for item in basket
        if (item.series_id or item.id) in flagged
    }
    costly_flagged = [item_id for item_id in costly_ids if item_id in flagged]
    costly_unknown = [item_id for item_id in costly_ids if item_id in unknown]
    if len(flagged) >= 3 and len(domains) >= 3 and len(sources) >= 3 and costly_flagged:
        return "protocol_coincidence"
    if len(flagged) >= 2 and costly_unknown and not costly_flagged:
        return "soft_flags_costly_unknown"
    if len(flagged) >= 2 and not costly_flagged and not costly_unknown:
        return "cheap_talk_without_costly"
    if flagged:
        return "isolated_flag"
    if unknown:
        return "quiet_with_unknowns"
    return "quiet"


def _alerts_for(flags: list[FlaggedSeries], protocol: dict[str, Any]) -> list[Any]:
    days = []
    by_key: dict[tuple[str, date], list[FlaggedSeries]] = {}
    for flag in flags:
        by_key.setdefault((flag.period_id, flag.day), []).append(flag)
    for _key, group in by_key.items():
        day = basket_day(
            group,
            k=int(protocol.get("k", 3)),
            k_costly=int(protocol.get("k_costly", 1)),
            k_domains=int(protocol.get("k_domains", 3)),
            require_distinct_families=bool(protocol.get("k_distinct_families", False)),
            require_distinct_sources=bool(protocol.get("k_distinct_source_systems", True)),
        )
        if day:
            days.append(day)
    return alerts_from_basket_days(days, persistence_days=int(protocol.get("persistence_days", 3)))


def _count_verdicts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    return counts


def _load_observations(collection_dir: Path, manifest: dict[str, Any]) -> list[Observation]:
    rows: list[Observation] = []
    for item in manifest.get("items", []):
        relative = item.get("observations")
        if not relative:
            continue
        path = collection_dir / relative
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(Observation.model_validate_json(line))
    if not rows:
        raise ValueError("collection has no observation files to measure")
    return rows


def _markdown(
    summary: dict[str, Any], days: list[dict[str, Any]], basket: list[IndicatorSpec]
) -> str:
    series = [item.series_id or item.id for item in basket]
    lines = [
        f"# Measurement {summary['measure_id']}",
        "",
        f"- Scenario: `{summary['scenario_id']}`",
        f"- Collection: `{summary['collection_id']}`",
        (
            f"- Protocol: `{summary['protocol_id']}` "
            f"(alerts require n_baseline ≥ {summary['protocol_n_min']})"
        ),
        f"- Exploratory n_min: {summary['exploratory_n_min']} (not coincidence_v0)",
        "- Missing/cloudy/source_down = **unknown threat**, not normal activity.",
        "- Protocol coincidence requires distinct **causal domains**, not merely source families.",
        f"- Protocol coincidence episodes: {len(summary['protocol_alerts'])}",
        f"- Exploratory coincidence episodes: {len(summary['exploratory_alerts'])}",
        "",
        "## Verdict counts",
        "",
    ]
    for key, value in sorted(summary["verdict_counts"].items()):
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Daily states", ""]
    header = "| Window | Day | Verdict | " + " | ".join(series) + " |"
    lines += [header, "|---|---|---|" + "|".join(["---"] * len(series)) + "|"]
    for row in days:
        cells = " | ".join(row["states"].get(item, "") for item in series)
        lines.append(
            f"| {row['window_id']} | {row['day']} | `{row['verdict']}` | {cells} |"
        )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
