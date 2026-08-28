from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from wsf.types import Alert, CostClass, Family


@dataclass(frozen=True)
class FlaggedSeries:
    period_id: str
    day: date
    series_id: str
    family: Family
    source_system: str
    cost_class: CostClass


@dataclass(frozen=True)
class BasketDay:
    period_id: str
    day: date
    flags: tuple[FlaggedSeries, ...]


def basket_day(
    flags: Iterable[FlaggedSeries],
    *,
    k: int,
    k_costly: int,
) -> BasketDay | None:
    unique = {flag.series_id: flag for flag in flags}
    values = tuple(sorted(unique.values(), key=lambda item: item.series_id))
    if not values:
        return None
    periods = {item.period_id for item in values}
    days = {item.day for item in values}
    if len(periods) != 1 or len(days) != 1:
        raise ValueError("basket_day requires flags from one period and date")
    if len(values) < k:
        return None
    if len({item.family for item in values}) < k:
        return None
    if len({item.source_system for item in values}) < k:
        return None
    if sum(item.cost_class is CostClass.costly for item in values) < k_costly:
        return None
    return BasketDay(period_id=values[0].period_id, day=values[0].day, flags=values)


def alerts_from_basket_days(
    days: Iterable[BasketDay],
    *,
    persistence_days: int,
) -> list[Alert]:
    if persistence_days < 1:
        raise ValueError("persistence_days must be positive")
    ordered = sorted(days, key=lambda item: (item.period_id, item.day))
    confirmations: list[BasketDay] = []
    by_key = {(item.period_id, item.day): item for item in ordered}
    for item in ordered:
        required = [item.day - timedelta(days=offset) for offset in range(persistence_days)]
        if all((item.period_id, required_day) in by_key for required_day in required):
            confirmations.append(item)

    episodes: list[list[BasketDay]] = []
    for item in confirmations:
        if (
            not episodes
            or episodes[-1][-1].period_id != item.period_id
            or item.day != episodes[-1][-1].day + timedelta(days=1)
        ):
            episodes.append([item])
        else:
            episodes[-1].append(item)

    alerts: list[Alert] = []
    for episode in episodes:
        flags = {flag.series_id: flag for item in episode for flag in item.flags}
        alerts.append(
            Alert(
                period_id=episode[0].period_id,
                start=episode[0].day,
                end=episode[-1].day,
                n_flagged=len(flags),
                n_costly_flagged=sum(
                    flag.cost_class is CostClass.costly for flag in flags.values()
                ),
                contributing_families=sorted({flag.family.value for flag in flags.values()}),
                contributing_source_systems=sorted({flag.source_system for flag in flags.values()}),
                contributing_series=sorted(flags),
            )
        )
    return alerts
