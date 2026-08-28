from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from wsf.protocol import SCIENTIFIC_CONFIG_FILES, load_yaml, scientific_config_hashes
from wsf.types import CausalDomain, Family, IndicatorSpec, IndicatorStatus, PeriodWindow


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def validate_configuration(config_dir: Path) -> dict[str, Any]:
    for filename in SCIENTIFIC_CONFIG_FILES:
        if not (config_dir / filename).is_file():
            raise FileNotFoundError(f"Missing scientific configuration: {filename}")

    indicators_data = load_yaml(config_dir / "indicator_register.yaml")
    indicators = TypeAdapter(list[IndicatorSpec]).validate_python(indicators_data)
    ids = [indicator.id for indicator in indicators]
    if len(ids) != len(set(ids)):
        raise ValueError("indicator ids must be unique")
    present_families = {indicator.family for indicator in indicators}
    missing_families = set(Family) - present_families
    if missing_families:
        missing = ", ".join(sorted(family.value for family in missing_families))
        raise ValueError(f"indicator register is missing families: {missing}")
    present_domains = {item.causal_domain for item in indicators if item.causal_domain}
    missing_domains = set(CausalDomain) - present_domains
    if missing_domains:
        missing = ", ".join(sorted(domain.value for domain in missing_domains))
        raise ValueError(f"indicator register is missing causal domains: {missing}")

    expected_baselines = load_yaml(config_dir / "expected_baselines.yaml") or []
    if not isinstance(expected_baselines, list):
        raise ValueError("expected_baselines.yaml must be a list")
    baseline_ids = {
        item["id"] for item in expected_baselines if isinstance(item, dict) and "id" in item
    }
    for indicator in indicators:
        if indicator.expected_baseline_id and indicator.expected_baseline_id not in baseline_ids:
            raise ValueError(f"{indicator.id}: unknown expected baseline")
        if (
            indicator.family is Family.coverage_asymmetry
            and indicator.status is not IndicatorStatus.uninstantiated
        ):
            raise ValueError("coverage_asymmetry must remain uninstantiated in v0")

    panel_data = load_yaml(config_dir / "period_panel.yaml")
    periods = TypeAdapter(list[PeriodWindow]).validate_python(panel_data)
    if len(periods) != 5:
        raise ValueError("v0 period panel must contain exactly five windows")

    queries = _require_mapping(load_yaml(config_dir / "queries.yaml"), "queries.yaml")
    query_periods = _require_mapping(queries.get("periods"), "queries.yaml periods")
    for period in periods:
        if period.query_id not in query_periods:
            raise ValueError(f"{period.id}: missing query configuration")

    milestones = _require_mapping(load_yaml(config_dir / "milestones.yaml"), "milestones")
    for period_id, milestone in milestones.items():
        provenance = milestone.get("provenance", []) if isinstance(milestone, dict) else []
        if not provenance or any(not item.get("url") for item in provenance):
            raise ValueError(f"{period_id}: milestones require provenance URLs")

    protocol = _require_mapping(load_yaml(config_dir / "protocol.yaml"), "protocol")
    if protocol.get("logistic") is not False:
        raise ValueError("v0 requires logistic: false")
    if protocol.get("covar_short_min_n", 0) > protocol.get("covar_short_days", 0):
        raise ValueError("covar_short_min_n cannot exceed covar_short_days")
    if protocol.get("viirs_availability_regime") != "reconstructed_assumed_latency":
        raise ValueError("v0 requires the declared VIIRS reconstruction regime")
    if protocol.get("k_distinct_causal_domains") is not True:
        raise ValueError("v1 requires coincidence across causal domains")
    if int(protocol.get("k_domains") or 0) < int(protocol.get("k") or 0):
        raise ValueError("k_domains must be at least k")

    interpretation = _require_mapping(
        load_yaml(config_dir / "interpretation_protocol.yaml"), "interpretation_protocol"
    )
    if interpretation.get("model") != "qwen3.8:27b-mlx":
        raise ValueError("unexpected Ollama model")
    if interpretation.get("repeats") != 5:
        raise ValueError("intent_triage_v0 requires five repeats")

    hashes = scientific_config_hashes(config_dir)
    return {
        "indicator_count": len(indicators),
        "period_count": len(periods),
        "config_hashes": hashes,
    }
