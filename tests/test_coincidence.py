from datetime import date, timedelta

from wsf.features.coincidence import FlaggedSeries, alerts_from_basket_days, basket_day
from wsf.types import CausalDomain, CostClass, Family

START = date(2021, 1, 1)


def flag(
    day_offset: int,
    series_id: str,
    family: Family,
    source_system: str,
    cost_class: CostClass,
    causal_domain: CausalDomain,
) -> FlaggedSeries:
    return FlaggedSeries(
        period_id="fixture-period",
        day=START + timedelta(days=day_offset),
        series_id=series_id,
        family=family,
        source_system=source_system,
        cost_class=cost_class,
        causal_domain=causal_domain,
    )


def valid_flags(day_offset: int) -> list[FlaggedSeries]:
    return [
        flag(
            day_offset,
            "tempo.viirs_aoi",
            Family.facility_tempo,
            "viirs_c2",
            CostClass.costly,
            CausalDomain.physical_activity,
        ),
        flag(
            day_offset,
            "talk.gdelt_cameo",
            Family.cheap_talk_vs_costly_motion,
            "gdelt_events",
            CostClass.soft,
            CausalDomain.information,
        ),
        flag(
            day_offset,
            "attn.wiki_pageviews",
            Family.attention_without_admission,
            "wikipedia",
            CostClass.soft,
            CausalDomain.public_attention,
        ),
    ]


def test_soft_only_flags_cannot_form_a_basket() -> None:
    flags = valid_flags(0)
    flags[0] = flag(
        0,
        "soft.third",
        Family.dyadic_counterpart,
        "alfred",
        CostClass.soft,
        CausalDomain.market,
    )
    assert basket_day(flags, k=3, k_costly=1) is None


def test_same_causal_domain_or_source_clones_cannot_form_a_basket() -> None:
    same_domain = [
        flag(
            0,
            "tempo.viirs_aoi",
            Family.facility_tempo,
            "viirs_c2",
            CostClass.costly,
            CausalDomain.physical_activity,
        ),
        flag(
            0,
            "tempo.s1_backscatter",
            Family.facility_tempo,
            "copernicus_s1",
            CostClass.costly,
            CausalDomain.physical_activity,
        ),
        flag(
            0,
            "tempo.firms_thermal",
            Family.facility_tempo,
            "nasa_firms",
            CostClass.costly,
            CausalDomain.physical_activity,
        ),
    ]
    assert basket_day(same_domain, k=3, k_costly=1) is None

    gdelt_icews_viirs = [
        flag(
            0,
            "talk.gdelt_cameo",
            Family.cheap_talk_vs_costly_motion,
            "gdelt_events",
            CostClass.soft,
            CausalDomain.information,
        ),
        flag(
            0,
            "talk.icews_cameo",
            Family.cheap_talk_vs_costly_motion,
            "icews",
            CostClass.soft,
            CausalDomain.information,
        ),
        flag(
            0,
            "tempo.viirs_aoi",
            Family.facility_tempo,
            "viirs_c2",
            CostClass.costly,
            CausalDomain.physical_activity,
        ),
    ]
    # Independent coding of overlapping public reporting is not a third domain.
    assert basket_day(gdelt_icews_viirs, k=3, k_costly=1) is None

    same_source = [
        FlaggedSeries(
            period_id=item.period_id,
            day=item.day,
            series_id=item.series_id,
            family=item.family,
            source_system="shared-pipeline",
            cost_class=item.cost_class,
            causal_domain=item.causal_domain,
        )
        for item in valid_flags(0)
    ]
    assert basket_day(same_source, k=3, k_costly=1) is None


def test_cross_domain_physical_bureaucratic_digital_can_form_a_basket() -> None:
    flags = [
        flag(
            0,
            "tempo.s1_backscatter",
            Family.facility_tempo,
            "copernicus_s1",
            CostClass.costly,
            CausalDomain.physical_activity,
        ),
        flag(
            0,
            "official.gazette",
            Family.official_residue,
            "internet_archive",
            CostClass.info,
            CausalDomain.bureaucratic,
        ),
        flag(
            0,
            "net.ripe_prefixes",
            Family.official_residue,
            "ripe_ris",
            CostClass.info,
            CausalDomain.digital_infrastructure,
        ),
    ]
    basket = basket_day(flags, k=3, k_costly=1)
    assert basket is not None


def test_three_day_persistence_confirms_on_day_six_and_closes_on_day_seven() -> None:
    basket_days = [
        basket_day(valid_flags(day_offset), k=3, k_costly=1) for day_offset in range(3, 7)
    ]
    alerts = alerts_from_basket_days(
        [item for item in basket_days if item is not None],
        persistence_days=3,
    )
    assert len(alerts) == 1
    assert alerts[0].start == START + timedelta(days=5)
    assert alerts[0].end == START + timedelta(days=6)
    assert alerts[0].n_costly_flagged == 1
    assert alerts[0].contributing_source_systems == ["gdelt_events", "viirs_c2", "wikipedia"]
    assert alerts[0].contributing_causal_domains == [
        "information",
        "physical_activity",
        "public_attention",
    ]


def test_one_day_gap_starts_a_new_episode() -> None:
    offsets = [0, 1, 2, 4, 5, 6]
    days = [basket_day(valid_flags(offset), k=3, k_costly=1) for offset in offsets]
    alerts = alerts_from_basket_days(
        [item for item in days if item is not None],
        persistence_days=3,
    )
    assert [(item.start, item.end) for item in alerts] == [
        (START + timedelta(days=2), START + timedelta(days=2)),
        (START + timedelta(days=6), START + timedelta(days=6)),
    ]
