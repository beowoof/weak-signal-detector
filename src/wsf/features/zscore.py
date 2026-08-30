from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta

from wsf.features.cutoff import as_of_value, select_expected_current
from wsf.types import FeatureRow, Observation, Polarity


def is_flagged(z: float, threshold: float, polarity: Polarity) -> bool:
    if polarity is Polarity.high_unusual:
        return z >= threshold
    if polarity is Polarity.low_unusual:
        return z <= -threshold
    return abs(z) >= threshold


def build_feature(
    observations: Iterable[Observation],
    *,
    period_id: str,
    series_id: str,
    cutoff_day: date,
    expected_lag_days: int,
    window_days: int,
    n_min: int,
    threshold: float,
    polarity: Polarity = Polarity.high_unusual,
) -> FeatureRow:
    relevant = [
        item for item in observations if item.period_id == period_id and item.series_id == series_id
    ]
    expected = cutoff_day - timedelta(days=expected_lag_days)
    current = select_expected_current(
        relevant,
        cutoff_day,
        expected_lag_days=expected_lag_days,
    )
    if current is None:
        return _missing_feature(period_id, series_id, cutoff_day, expected)

    by_event_time: dict[object, list[Observation]] = defaultdict(list)
    baseline_start = current.event_time - timedelta(days=window_days)
    for item in relevant:
        if baseline_start <= item.event_time < current.event_time:
            by_event_time[item.event_time].append(item)

    baseline_values: list[float] = []
    for versions in by_event_time.values():
        selected = as_of_value(versions, cutoff_day)
        if selected and selected.quality == "ok" and selected.value is not None:
            baseline_values.append(selected.value)

    if len(baseline_values) < n_min:
        return _missing_feature(
            period_id,
            series_id,
            cutoff_day,
            expected,
            current=current,
            raw=current.value,
            n_baseline=len(baseline_values),
        )

    baseline_mu = statistics.fmean(baseline_values)
    baseline_sigma = statistics.pstdev(baseline_values)
    if baseline_sigma == 0:
        if current.value is None:
            raise ValueError("current observation unexpectedly has no value")
        return FeatureRow(
            period_id=period_id,
            series_id=series_id,
            cutoff=cutoff_day,
            expected_event_date=expected,
            current_event_time=current.event_time,
            age_days=(cutoff_day - current.event_time.date()).days,
            raw=current.value,
            baseline_mu=baseline_mu,
            baseline_sigma=baseline_sigma,
            n_baseline=len(baseline_values),
            z=None,
            missing=False,
            silence=False,
            flagged=_constant_baseline_flagged(current.value, baseline_mu, polarity),
        )

    if current.value is None:  # guarded by select_expected_current; keeps typing explicit
        raise ValueError("current observation unexpectedly has no value")
    z = (current.value - baseline_mu) / baseline_sigma
    return FeatureRow(
        period_id=period_id,
        series_id=series_id,
        cutoff=cutoff_day,
        expected_event_date=expected,
        current_event_time=current.event_time,
        age_days=(cutoff_day - current.event_time.date()).days,
        raw=current.value,
        baseline_mu=baseline_mu,
        baseline_sigma=baseline_sigma,
        n_baseline=len(baseline_values),
        z=z,
        missing=False,
        silence=False,
        flagged=is_flagged(z, threshold, polarity),
    )


def _constant_baseline_flagged(value: float, baseline: float, polarity: Polarity) -> bool:
    if polarity is Polarity.high_unusual:
        return value > baseline
    if polarity is Polarity.low_unusual:
        return value < baseline
    return value != baseline


def _missing_feature(
    period_id: str,
    series_id: str,
    cutoff_day: date,
    expected: date,
    *,
    current: Observation | None = None,
    raw: float | None = None,
    baseline_mu: float | None = None,
    baseline_sigma: float | None = None,
    n_baseline: int = 0,
) -> FeatureRow:
    return FeatureRow(
        period_id=period_id,
        series_id=series_id,
        cutoff=cutoff_day,
        expected_event_date=expected,
        current_event_time=current.event_time if current else None,
        age_days=(cutoff_day - current.event_time.date()).days if current else None,
        raw=raw,
        baseline_mu=baseline_mu,
        baseline_sigma=baseline_sigma,
        n_baseline=n_baseline,
        z=None,
        missing=True,
        silence=False,
        flagged=False,
    )
