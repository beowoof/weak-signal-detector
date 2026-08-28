from datetime import UTC, date, datetime, timedelta

import pytest

from wsf.features.zscore import build_feature, is_flagged
from wsf.types import Observation, Polarity


def observation(day: date, value: float, version: str | None = None) -> Observation:
    event_time = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    return Observation(
        version_id=version or f"v-{day.isoformat()}",
        series_id="fixture.series",
        period_id="fixture-period",
        event_time=event_time,
        available_at=event_time + timedelta(hours=12),
        retrieved_at=datetime(2026, 8, 28, tzinfo=UTC),
        value=value,
        quality="ok",
    )


def baseline_and_current() -> tuple[list[Observation], date]:
    current_day = date(2021, 2, 1)
    rows = []
    for offset in range(20, 0, -1):
        value = 0.0 if offset % 2 == 0 else 2.0
        rows.append(observation(current_day - timedelta(days=offset), value))
    rows.append(observation(current_day, 3.5))
    return rows, current_day


def test_current_is_excluded_from_population_baseline() -> None:
    rows, current_day = baseline_and_current()
    feature = build_feature(
        rows,
        period_id="fixture-period",
        series_id="fixture.series",
        cutoff_day=current_day,
        expected_lag_days=0,
        window_days=90,
        n_min=20,
        threshold=2.5,
    )
    assert feature.missing is False
    assert feature.baseline_mu == 1.0
    assert feature.baseline_sigma == 1.0
    assert feature.n_baseline == 20
    assert feature.z == 2.5
    assert feature.flagged is True


def test_missing_quality_is_unknown_not_normal_or_silent() -> None:
    rows, current_day = baseline_and_current()
    cloudy = observation(current_day, 0.0)
    cloudy.quality = "missing"
    cloudy.value = None
    rows[-1] = cloudy
    feature = build_feature(
        rows,
        period_id="fixture-period",
        series_id="fixture.series",
        cutoff_day=current_day,
        expected_lag_days=0,
        window_days=90,
        n_min=20,
        threshold=2.5,
    )
    assert feature.missing is True
    assert feature.silence is False
    assert feature.flagged is False
    assert feature.z is None


def test_insufficient_baseline_is_missing_and_never_flags() -> None:
    rows, current_day = baseline_and_current()
    feature = build_feature(
        rows,
        period_id="fixture-period",
        series_id="fixture.series",
        cutoff_day=current_day,
        expected_lag_days=0,
        window_days=90,
        n_min=21,
        threshold=2.5,
    )
    assert feature.missing is True
    assert feature.z is None
    assert feature.flagged is False


@pytest.mark.parametrize(
    ("z", "polarity", "expected"),
    [
        (2.5, Polarity.high_unusual, True),
        (-2.5, Polarity.high_unusual, False),
        (-2.5, Polarity.low_unusual, True),
        (-2.5, Polarity.either, True),
    ],
)
def test_polarity_is_explicit(z: float, polarity: Polarity, expected: bool) -> None:
    assert is_flagged(z, 2.5, polarity) is expected
