from __future__ import annotations

from datetime import date, timedelta

from wsf.features.coincidence import FlaggedSeries
from wsf.features.permutation import (
    amber_days,
    chorus_counts,
    max_run_length,
    permute_amber,
    permute_independence,
)
from wsf.types import CausalDomain, CostClass, Family

PROTOCOL = {
    "k": 3,
    "k_costly": 1,
    "k_domains": 3,
    "k_distinct_families": False,
    "k_distinct_source_systems": True,
    "persistence_days": 3,
}

START = date(2022, 2, 1)


def _flag(
    offset: int,
    series: str,
    domain: CausalDomain,
    source: str,
    cost: CostClass,
) -> FlaggedSeries:
    family = (
        Family.facility_tempo if cost is CostClass.costly else Family.attention_without_admission
    )
    return FlaggedSeries(
        period_id="incident",
        day=START + timedelta(days=offset),
        series_id=series,
        family=family,
        source_system=source,
        cost_class=cost,
        causal_domain=domain,
    )


def _trio(offset: int) -> list[FlaggedSeries]:
    return [
        _flag(offset, "tempo.viirs_aoi", CausalDomain.physical_activity, "viirs", CostClass.costly),
        _flag(offset, "talk.gdelt_cameo", CausalDomain.information, "gdelt", CostClass.soft),
        _flag(
            offset,
            "attn.wiki_pageviews",
            CausalDomain.public_attention,
            "wikipedia",
            CostClass.soft,
        ),
    ]


def _aligned_chorus() -> list[FlaggedSeries]:
    flags: list[FlaggedSeries] = []
    for offset in range(3):
        flags.extend(_trio(offset))
    return flags


def test_aligned_three_days_is_one_episode() -> None:
    counts = chorus_counts(_aligned_chorus(), protocol=PROTOCOL)
    assert counts["n_basket_days"] == 3
    assert counts["n_episodes"] == 1


def test_permutation_penalises_perfect_alignment_more_than_spread() -> None:
    days = [START + timedelta(days=offset) for offset in range(12)]
    aligned = permute_independence(_aligned_chorus(), days, protocol=PROTOCOL, n_perm=200, seed=1)
    spread = [
        _flag(0, "tempo.viirs_aoi", CausalDomain.physical_activity, "viirs", CostClass.costly),
        _flag(4, "talk.gdelt_cameo", CausalDomain.information, "gdelt", CostClass.soft),
        _flag(
            8,
            "attn.wiki_pageviews",
            CausalDomain.public_attention,
            "wikipedia",
            CostClass.soft,
        ),
    ]
    unaligned = permute_independence(spread, days, protocol=PROTOCOL, n_perm=200, seed=1)
    assert aligned["observed_basket_days"] == 3
    assert unaligned["observed_basket_days"] == 0
    assert aligned["p_basket_days"] < unaligned["p_basket_days"]
    assert aligned["method"] == "independent_circular_shift_within_available_days"


def test_permutation_preserves_each_series_availability_mask() -> None:
    days = [START + timedelta(days=offset) for offset in range(12)]
    flags = _aligned_chorus()
    availability = {
        "tempo.viirs_aoi": [days[index] for index in (0, 1, 2, 4, 6, 8, 10)],
        "talk.gdelt_cameo": days,
        "attn.wiki_pageviews": days,
    }
    result = permute_independence(
        flags,
        days,
        protocol=PROTOCOL,
        n_perm=50,
        seed=7,
        available_days=availability,
    )
    assert result["available_day_counts"]["tempo.viirs_aoi"] == 7
    assert result["available_day_counts"]["talk.gdelt_cameo"] == 12


def _soft(offset: int, series: str, domain: CausalDomain, source: str) -> FlaggedSeries:
    return _flag(offset, series, domain, source, CostClass.soft)


def _soft_pair(offset: int) -> list[FlaggedSeries]:
    return [
        _soft(offset, "talk.gdelt_cameo", CausalDomain.information, "gdelt"),
        _soft(
            offset,
            "attn.wiki_pageviews",
            CausalDomain.public_attention,
            "wikipedia",
        ),
    ]


def test_amber_requires_two_domains_on_a_frozen_unknown_night() -> None:
    days = [START + timedelta(days=offset) for offset in range(6)]
    cloudy = {START, START + timedelta(days=1), START + timedelta(days=2)}
    aligned = [flag for offset in range(3) for flag in _soft_pair(offset)]
    marked = amber_days(
        aligned,
        days,
        costly_unknown_days=cloudy,
        costly_flagged_days=set(),
    )
    assert marked == cloudy
    assert max_run_length(days, marked) == 3
    same_domain = [
        _soft(offset, "talk.gdelt_cameo", CausalDomain.information, "gdelt")
        for offset in range(3)
    ] + [
        _soft(offset, "talk.icews_cameo", CausalDomain.information, "icews")
        for offset in range(3)
    ]
    assert (
        amber_days(same_domain, days, costly_unknown_days=cloudy, costly_flagged_days=set())
        == set()
    )


def test_amber_permutation_holds_the_viirs_cloud_mask_fixed() -> None:
    days = [START + timedelta(days=offset) for offset in range(12)]
    cloudy = {days[0], days[1], days[2]}
    flags = [flag for offset in range(3) for flag in _soft_pair(offset)]
    result = permute_amber(
        flags,
        days,
        protocol={**PROTOCOL, "amber_persistence_days": 3},
        n_perm=200,
        seed=3,
        available_days={
            "talk.gdelt_cameo": days,
            "attn.wiki_pageviews": days,
        },
        costly_unknown_days=cloudy,
        costly_flagged_days=set(),
    )
    assert result["observed_max_run"] == 3
    assert result["observed_episodes"] == 1
    assert result["frozen_costly_unknown_days"] == 3
    assert result["method"] == "independent_circular_shift_soft_flags_frozen_costly_mask"
    assert result["p_max_run"] is not None
    assert result["p_max_run"] < 0.2


def test_amber_permutation_is_uninformative_when_soft_flags_are_always_on() -> None:
    days = [START + timedelta(days=offset) for offset in range(12)]
    cloudy = {days[0], days[1], days[2]}
    flags = [flag for offset in range(12) for flag in _soft_pair(offset)]
    result = permute_amber(
        flags,
        days,
        protocol={**PROTOCOL, "amber_persistence_days": 3},
        n_perm=100,
        seed=1,
        available_days={
            "talk.gdelt_cameo": days,
            "attn.wiki_pageviews": days,
        },
        costly_unknown_days=cloudy,
        costly_flagged_days=set(),
    )
    assert result["observed_max_run"] == 3
    assert result["p_max_run"] == 1.0


def test_costly_flagged_nights_never_count_as_amber_even_if_another_costly_is_unknown() -> None:
    days = [START + timedelta(days=offset) for offset in range(6)]
    flags = [flag for offset in range(3) for flag in _soft_pair(offset)]
    marked = amber_days(
        flags,
        days,
        costly_unknown_days={days[0], days[1], days[2]},
        costly_flagged_days={days[0], days[1], days[2]},
    )
    assert marked == set()
    result = permute_amber(
        flags,
        days,
        protocol={**PROTOCOL, "amber_persistence_days": 3},
        n_perm=50,
        seed=2,
        available_days={
            "talk.gdelt_cameo": days,
            "attn.wiki_pageviews": days,
        },
        costly_unknown_days={days[0], days[1], days[2]},
        costly_flagged_days={days[0], days[1], days[2]},
    )
    assert result["observed_max_run"] == 0
    assert result["p_max_run"] == 1.0
