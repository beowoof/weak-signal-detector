from __future__ import annotations

from datetime import date, timedelta

from wsf.features.coincidence import FlaggedSeries
from wsf.features.permutation import chorus_counts, permute_independence
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
    aligned = permute_independence(
        _aligned_chorus(), days, protocol=PROTOCOL, n_perm=200, seed=1
    )
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
