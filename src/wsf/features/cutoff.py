from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from wsf.time import cutoff_instant, expected_event_date
from wsf.types import Observation


def as_of_value(versions: Iterable[Observation], cutoff_day: date) -> Observation | None:
    cutoff = cutoff_instant(cutoff_day)
    visible = [version for version in versions if version.available_at <= cutoff]
    if not visible:
        return None
    return max(visible, key=lambda version: (version.available_at, version.version_id))


def select_expected_row(
    observations: Iterable[Observation],
    cutoff_day: date,
    *,
    expected_lag_days: int,
) -> Observation | None:
    """Select the exact expected event date regardless of quality; never stale-carry."""
    expected = expected_event_date(cutoff_day, expected_lag_days)
    candidates = [item for item in observations if item.event_time.date() == expected]
    return as_of_value(candidates, cutoff_day)


def select_expected_current(
    observations: Iterable[Observation],
    cutoff_day: date,
    *,
    expected_lag_days: int,
) -> Observation | None:
    """Select the exact expected event date; never fall back to stale data."""
    selected = select_expected_row(
        observations, cutoff_day, expected_lag_days=expected_lag_days
    )
    if selected is None or selected.quality != "ok" or selected.value is None:
        return None
    return selected
