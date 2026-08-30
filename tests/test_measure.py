from __future__ import annotations

import json
from pathlib import Path

import pytest

from wsf.measure import (
    _active_basket,
    _day_verdict,
    _evidence_gap_episodes,
    _measurement_mode,
    _permute_amber_windows,
)
from wsf.types import (
    CausalDomain,
    CostClass,
    Family,
    IndicatorSpec,
    IndicatorStatus,
    Polarity,
    SubjectControl,
)


def _indicator(
    series_id: str,
    family: Family,
    cost: CostClass,
    source: str,
    domain: CausalDomain,
) -> IndicatorSpec:
    return IndicatorSpec(
        id=series_id,
        family=family,
        hypothesis="fixture",
        status=IndicatorStatus.instantiated,
        cost_class=cost,
        polarity=Polarity.high_unusual,
        in_basket=True,
        source_system=source,
        connector=source,
        series_id=series_id,
        causal_domain=domain,
        collector="fixture",
        subject_controls_signal=SubjectControl.no,
    )


BASKET = [
    _indicator(
        "tempo.viirs_aoi",
        Family.facility_tempo,
        CostClass.costly,
        "viirs",
        CausalDomain.physical_activity,
    ),
    _indicator(
        "talk.gdelt_cameo",
        Family.cheap_talk_vs_costly_motion,
        CostClass.soft,
        "gdelt",
        CausalDomain.information,
    ),
    _indicator(
        "attn.wiki_pageviews",
        Family.attention_without_admission,
        CostClass.soft,
        "wikipedia",
        CausalDomain.public_attention,
    ),
]


def test_cloudy_costly_source_is_unknown_not_quiet() -> None:
    states = {
        "tempo.viirs_aoi": "unknown",
        "talk.gdelt_cameo": "flagged",
        "attn.wiki_pageviews": "flagged",
    }
    assert _day_verdict(states, BASKET) == "soft_flags_costly_unknown"


def test_normal_costly_with_soft_flags_is_cheap_talk_not_unknown() -> None:
    states = {
        "tempo.viirs_aoi": "normal",
        "talk.gdelt_cameo": "flagged",
        "attn.wiki_pageviews": "flagged",
    }
    assert _day_verdict(states, BASKET) == "cheap_talk_without_costly"


def test_all_normal_is_quiet() -> None:
    states = {
        "tempo.viirs_aoi": "normal",
        "talk.gdelt_cameo": "normal",
        "attn.wiki_pageviews": "normal",
    }
    assert _day_verdict(states, BASKET) == "quiet"


def test_three_physical_sensors_are_not_protocol_coincidence() -> None:
    physical = [
        _indicator(
            "tempo.viirs_aoi",
            Family.facility_tempo,
            CostClass.costly,
            "viirs",
            CausalDomain.physical_activity,
        ),
        _indicator(
            "tempo.s1_backscatter",
            Family.facility_tempo,
            CostClass.costly,
            "sar",
            CausalDomain.physical_activity,
        ),
        _indicator(
            "tempo.firms_thermal",
            Family.facility_tempo,
            CostClass.costly,
            "firms",
            CausalDomain.physical_activity,
        ),
    ]
    states = {
        "tempo.viirs_aoi": "flagged",
        "tempo.s1_backscatter": "flagged",
        "tempo.firms_thermal": "flagged",
    }
    assert _day_verdict(states, physical) == "same_domain_cluster"


def test_cross_domain_flags_are_protocol_coincidence() -> None:
    states = {
        "tempo.viirs_aoi": "flagged",
        "talk.gdelt_cameo": "flagged",
        "attn.wiki_pageviews": "flagged",
    }
    assert _day_verdict(states, BASKET) == "protocol_coincidence"


def test_same_domain_sources_do_not_create_an_amber_verdict() -> None:
    same_domain = [
        BASKET[0],
        _indicator(
            "talk.gdelt_cameo",
            Family.cheap_talk_vs_costly_motion,
            CostClass.soft,
            "gdelt",
            CausalDomain.information,
        ),
        _indicator(
            "talk.icews_cameo",
            Family.cheap_talk_vs_costly_motion,
            CostClass.soft,
            "icews",
            CausalDomain.information,
        ),
    ]
    states = {
        "tempo.viirs_aoi": "unknown",
        "talk.gdelt_cameo": "flagged",
        "talk.icews_cameo": "flagged",
    }
    assert _day_verdict(states, same_domain) == "same_domain_cluster"


def test_three_day_cross_domain_data_gap_becomes_amber_episode() -> None:
    rows = [
        {
            "window_id": "incident",
            "day": f"2022-02-{day:02d}",
            "verdict": "soft_flags_costly_unknown",
            "rhythm_verdict": "soft_flags_costly_unknown",
            "states": {
                "tempo.viirs_aoi": "unknown",
                "talk.gdelt_cameo": "flagged",
                "attn.wiki_pageviews": "flagged",
            },
            "rhythm_states": {
                "tempo.viirs_aoi": "unknown",
                "talk.gdelt_cameo": "flagged",
                "attn.wiki_pageviews": "flagged",
            },
        }
        for day in (21, 22, 23)
    ]
    episodes = _evidence_gap_episodes(rows, BASKET, {"amber_persistence_days": 3}, rhythm=False)
    assert len(episodes) == 1
    assert episodes[0]["start"] == "2022-02-21"
    assert episodes[0]["contributing_causal_domains"] == [
        "information",
        "public_attention",
    ]


def test_amber_window_permutation_uses_max_run_and_frozen_costly_mask() -> None:
    rows = []
    for day in range(1, 13):
        cloudy = day <= 3
        rows.append(
            {
                "window_id": "incident",
                "day": f"2022-02-{day:02d}",
                "verdict": "soft_flags_costly_unknown" if cloudy else "isolated_flag",
                "rhythm_verdict": "quiet",
                "states": {
                    "tempo.viirs_aoi": "unknown" if cloudy else "normal",
                    "talk.gdelt_cameo": "flagged" if cloudy else "normal",
                    "attn.wiki_pageviews": "flagged" if cloudy else "normal",
                },
                "rhythm_states": {
                    "tempo.viirs_aoi": "normal",
                    "talk.gdelt_cameo": "normal",
                    "attn.wiki_pageviews": "normal",
                },
            }
        )
    protocol = {"amber_persistence_days": 3, "permutation_n": 80}
    result = _permute_amber_windows(
        rows,
        BASKET,
        protocol,
        "collection-fixture",
        "amber",
        rhythm=False,
    )
    stats = result["incident"]
    assert stats["observed_max_run"] == 3
    assert stats["observed_episodes"] == 1
    assert stats["frozen_costly_unknown_days"] == 3
    assert stats["p_max_run"] is not None
    assert stats["p_max_run"] < 0.25
    rhythm = _permute_amber_windows(
        rows,
        BASKET,
        protocol,
        "collection-fixture",
        "rhythm_amber",
        rhythm=True,
    )
    assert rhythm["incident"]["observed_max_run"] == 0
    assert rhythm["incident"]["p_max_run"] == 1.0


def test_active_basket_uses_only_materialised_collection_series() -> None:
    sar = _indicator(
        "tempo.s1_backscatter",
        Family.facility_tempo,
        CostClass.costly,
        "sar",
        CausalDomain.physical_activity,
    )
    manifest = {
        "items": [
            {
                "series_id": "tempo.viirs_aoi",
                "observations": "observations/viirs.jsonl",
                "not_applicable": False,
            }
        ]
    }
    active = _active_basket([*BASKET, sar], manifest)
    assert [item.series_id for item in active] == ["tempo.viirs_aoi"]


def test_unfrozen_measurement_requires_explicit_exploratory_mode(tmp_path: Path) -> None:
    status = {"active_review_id": "review-one"}
    review_dir = tmp_path / "reviews" / "review-one"
    review_dir.mkdir(parents=True)
    (review_dir / "decision.json").write_text(
        json.dumps({"decision": "model_pending"}), encoding="utf-8"
    )
    manifest = {"collection_id": "collection-one"}

    with pytest.raises(ValueError, match="Use --exploratory"):
        _measurement_mode(
            tmp_path,
            status,
            manifest,
            current_scenario_hash="scenario-hash",
            current_protocol_hash="protocol-hash",
            exploratory=False,
        )
    assert (
        _measurement_mode(
            tmp_path,
            status,
            manifest,
            current_scenario_hash="scenario-hash",
            current_protocol_hash="protocol-hash",
            exploratory=True,
        )
        == "exploratory_unfrozen"
    )


def test_matching_non_rehearsal_freeze_enables_scientific_mode(tmp_path: Path) -> None:
    (tmp_path / "freeze.json").write_text(
        json.dumps(
            {
                "collection_id": "collection-one",
                "scenario_hash": "scenario-hash",
                "protocol_hash": "protocol-hash",
                "rehearsal": False,
            }
        ),
        encoding="utf-8",
    )
    assert (
        _measurement_mode(
            tmp_path,
            {},
            {"collection_id": "collection-one"},
            current_scenario_hash="scenario-hash",
            current_protocol_hash="protocol-hash",
            exploratory=False,
        )
        == "frozen_protocol"
    )
