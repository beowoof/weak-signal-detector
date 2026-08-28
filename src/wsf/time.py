from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

UTC = UTC


def cutoff_instant(day: date) -> datetime:
    return datetime.combine(day, time(23, 59, 59), tzinfo=UTC)


def expected_event_date(cutoff_day: date, expected_lag_days: int) -> date:
    if expected_lag_days < 0:
        raise ValueError("expected_lag_days must be non-negative")
    return cutoff_day - timedelta(days=expected_lag_days)


def date_range(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end must not precede start")
    days: list[date] = []
    day = start
    while day <= end:
        days.append(day)
        day += timedelta(days=1)
    return days
