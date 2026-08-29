from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from wsf.features.coincidence import FlaggedSeries, alerts_from_basket_days, basket_day
from wsf.features.cutoff import select_expected_row
from wsf.features.permutation import permute_independence, seed_for
from wsf.features.rhythm import QuietPrior, build_quiet_priors, score_against_prior
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
    control = scenario.controls[0] if scenario.controls else None
    quiet_priors = (
        build_quiet_priors(
            observations,
            series_ids=[item.series_id or item.id for item in basket],
            control_period_id=control.id,
            prior_end=control.start,
        )
        if control is not None and control.start is not None
        else {}
    )
    measure_id = validate_run_id(run_id or new_run_id("measure"))
    out_dir = scenario_dir / "measurement" / measure_id
    out_dir.mkdir(parents=True, exist_ok=False)
    log.line(f"measure {scenario_id} collection={collection_id} series={len(basket)}")

    rows: list[dict[str, Any]] = []
    day_verdicts: list[dict[str, Any]] = []
    protocol_flags: list[FlaggedSeries] = []
    exploratory_flags: list[FlaggedSeries] = []
    rhythm_protocol_flags: list[FlaggedSeries] = []
    rhythm_exploratory_flags: list[FlaggedSeries] = []

    for window in windows:
        assert window.start is not None and window.end is not None
        days = date_range(window.start, window.end)
        for day in days:
            states: dict[str, str] = {}
            rhythm_states: dict[str, str] = {}
            for indicator in basket:
                scored = _score_series(
                    observations,
                    indicator=indicator,
                    window_id=window.id,
                    event_day=day,
                    protocol=protocol,
                    quiet_prior=quiet_priors.get(indicator.series_id or indicator.id),
                )
                rows.append(scored)
                series_id = indicator.series_id or indicator.id
                states[series_id] = scored["state"]
                rhythm_states[series_id] = str(scored.get("rhythm_state") or "unknown")
                flag = _as_flag(indicator, window.id, day, scored)
                if flag and scored["protocol_eligible"]:
                    protocol_flags.append(flag)
                if flag:
                    exploratory_flags.append(flag)
                rhythm_flag = _as_flag(
                    indicator, window.id, day, {**scored, "state": scored.get("rhythm_state")}
                )
                if rhythm_flag and scored.get("rhythm_protocol_eligible"):
                    rhythm_protocol_flags.append(rhythm_flag)
                if rhythm_flag:
                    rhythm_exploratory_flags.append(rhythm_flag)
            verdict = _day_verdict(states, basket)
            rhythm_verdict = _day_verdict(rhythm_states, basket)
            day_verdicts.append(
                {
                    "window_id": window.id,
                    "day": day.isoformat(),
                    "states": states,
                    "verdict": verdict,
                    "rhythm_states": rhythm_states,
                    "rhythm_verdict": rhythm_verdict,
                }
            )
            log.status(f"measure {window.id} {day.isoformat()} {verdict}/{rhythm_verdict}")

    protocol_alerts = _alerts_for(protocol_flags, protocol)
    exploratory_alerts = _alerts_for(exploratory_flags, protocol)
    rhythm_alerts = _alerts_for(rhythm_protocol_flags, protocol)
    rhythm_exploratory_alerts = _alerts_for(rhythm_exploratory_flags, protocol)
    log.status("permute trailing and rhythm flag calendars")
    permutation = {
        "trailing": _permute_windows(
            protocol_flags, day_verdicts, protocol, collection_id, "trailing"
        ),
        "rhythm": _permute_windows(
            rhythm_protocol_flags, day_verdicts, protocol, collection_id, "rhythm"
        ),
    }
    summary = {
        "measure_id": measure_id,
        "scenario_id": scenario_id,
        "collection_id": collection_id,
        "scenario_hash": scenario_hash(scenario),
        "protocol_id": protocol.get("protocol_id"),
        "exploratory_n_min": EXPLORATORY_N_MIN,
        "protocol_n_min": protocol.get("n_min"),
        "scientific_result": False,
        "quiet_prior_period": control.id if control is not None else None,
        "quiet_prior_end": control.start.isoformat() if control and control.start else None,
        "quiet_priors": {key: prior.summary() for key, prior in quiet_priors.items()},
        "notes": [
            "A missing or cloudy observation is unknown threat, not normal activity.",
            "Trailing z uses lookback in the same window (novelty vs recent history).",
            "Rhythm z uses the control lookback as a frozen quiet/seasonal prior.",
            "coincidence_v0 thresholds are unchanged. Rhythm is a parallel overlay.",
            "Coincidence is across causal domains, not merely source families.",
            "Permutation shuffles each series' flag days independently (marginals fixed).",
        ],
        "n_feature_rows": len(rows),
        "protocol_alerts": [item.model_dump(mode="json") for item in protocol_alerts],
        "exploratory_alerts": [item.model_dump(mode="json") for item in exploratory_alerts],
        "rhythm_alerts": [item.model_dump(mode="json") for item in rhythm_alerts],
        "rhythm_exploratory_alerts": [
            item.model_dump(mode="json") for item in rhythm_exploratory_alerts
        ],
        "verdict_counts": _count_verdicts(day_verdicts),
        "rhythm_verdict_counts": _count_verdicts(
            [{"verdict": row["rhythm_verdict"]} for row in day_verdicts]
        ),
        "permutation": permutation,
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
        f"protocol_alerts={len(protocol_alerts)} exploratory_alerts={len(exploratory_alerts)} "
        f"rhythm_alerts={len(rhythm_alerts)} "
        f"permute_incident_rhythm_p_basket="
        f"{(permutation.get('rhythm') or {}).get('incident', {}).get('p_basket_days')}"
    )
    return out_dir, summary


def _score_series(
    observations: list[Observation],
    *,
    indicator: IndicatorSpec,
    window_id: str,
    event_day: date,
    protocol: dict[str, Any],
    quiet_prior: QuietPrior | None = None,
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
        "rhythm_state": "unknown",
        "rhythm_z": None,
        "rhythm_quantile": None,
        "rhythm_n": 0,
        "rhythm_protocol_eligible": False,
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
    if quiet_prior is not None:
        payload.update(
            score_against_prior(
                float(observed.value),
                quiet_prior,
                threshold=float(protocol.get("z_threshold", 2.5)),
                polarity=indicator.polarity or Polarity.high_unusual,
                n_min=EXPLORATORY_N_MIN,
                protocol_n_min=int(protocol.get("n_min", 20)),
            )
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


def _permute_windows(
    flags: list[FlaggedSeries],
    days: list[dict[str, Any]],
    protocol: dict[str, Any],
    collection_id: str,
    kind: str,
) -> dict[str, Any]:
    n_perm = int(protocol.get("permutation_n", 1000))
    by_window: dict[str, list[date]] = {}
    for row in days:
        by_window.setdefault(row["window_id"], []).append(date.fromisoformat(row["day"]))
    result: dict[str, Any] = {}
    for window_id, window_days in by_window.items():
        window_flags = [flag for flag in flags if flag.period_id == window_id]
        result[window_id] = permute_independence(
            window_flags,
            window_days,
            protocol=protocol,
            n_perm=n_perm,
            seed=seed_for(collection_id, kind, window_id),
        )
    return result


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
        (
            f"- Rhythm coincidence episodes: {len(summary.get('rhythm_alerts') or [])} "
            "(quiet/seasonal prior; same k/domains/persistence)"
        ),
        "",
        "## Quiet prior (control lookback)",
        "",
    ]
    if summary.get("quiet_prior_period"):
        lines.append(
            f"- Period `{summary['quiet_prior_period']}` values strictly before "
            f"`{summary.get('quiet_prior_end')}`."
        )
    for key, prior in sorted((summary.get("quiet_priors") or {}).items()):
        lines.append(
            f"- `{key}`: n={prior.get('n')} μ={prior.get('mu')} σ={prior.get('sigma')}"
        )
    lines += ["", "## Trailing-z verdict counts", ""]
    for key, value in sorted(summary["verdict_counts"].items()):
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Rhythm verdict counts", ""]
    for key, value in sorted((summary.get("rhythm_verdict_counts") or {}).items()):
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Permutation (chorus vs independent kitchens)", ""]
    for kind, block in (summary.get("permutation") or {}).items():
        lines.append(f"### {kind}")
        for window_id, stats in block.items():
            lines.append(
                f"- `{window_id}`: observed basket days {stats.get('observed_basket_days')}, "
                f"episodes {stats.get('observed_episodes')}; "
                f"null mean basket {stats.get('null_basket_days_mean')}; "
                f"p_basket={stats.get('p_basket_days')}, p_episodes={stats.get('p_episodes')} "
                f"(n_perm={stats.get('n_perm')})"
            )
        lines.append("")
    lines += ["", "## Daily states (trailing z)", ""]
    header = "| Window | Day | Verdict | " + " | ".join(series) + " |"
    lines += [header, "|---|---|---|" + "|".join(["---"] * len(series)) + "|"]
    for row in days:
        cells = " | ".join(row["states"].get(item, "") for item in series)
        lines.append(
            f"| {row['window_id']} | {row['day']} | `{row['verdict']}` | {cells} |"
        )
    lines += ["", "## Daily states (rhythm vs quiet prior)", ""]
    lines += [header, "|---|---|---|" + "|".join(["---"] * len(series)) + "|"]
    for row in days:
        cells = " | ".join(row.get("rhythm_states", {}).get(item, "") for item in series)
        lines.append(
            f"| {row['window_id']} | {row['day']} | `{row.get('rhythm_verdict', '')}` | {cells} |"
        )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
