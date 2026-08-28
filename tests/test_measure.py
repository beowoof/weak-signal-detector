from __future__ import annotations

from wsf.measure import _day_verdict
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
    assert _day_verdict(states, physical) == "isolated_flag"


def test_cross_domain_flags_are_protocol_coincidence() -> None:
    states = {
        "tempo.viirs_aoi": "flagged",
        "talk.gdelt_cameo": "flagged",
        "attn.wiki_pageviews": "flagged",
    }
    assert _day_verdict(states, BASKET) == "protocol_coincidence"
