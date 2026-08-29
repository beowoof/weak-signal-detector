from __future__ import annotations

from datetime import UTC, date, datetime

from wsf.features.rhythm import build_quiet_priors, empirical_cdf, score_against_prior
from wsf.types import Observation, Polarity


def _obs(period: str, series: str, day: date, value: float) -> Observation:
    return Observation(
        version_id=f"{series}:{day.isoformat()}",
        series_id=series,
        period_id=period,
        event_time=datetime(day.year, day.month, day.day, tzinfo=UTC),
        available_at=datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=UTC),
        retrieved_at=datetime(2026, 8, 29, tzinfo=UTC),
        value=value,
        quality="ok",
    )


def test_quiet_prior_uses_control_lookback_not_scored_days() -> None:
    rows = [
        _obs("control", "wiki", date(2021, 1, 1), 10.0),
        _obs("control", "wiki", date(2021, 1, 2), 12.0),
        _obs("control", "wiki", date(2021, 2, 10), 999.0),
        _obs("incident", "wiki", date(2022, 2, 10), 50.0),
    ]
    priors = build_quiet_priors(
        rows,
        series_ids=["wiki"],
        control_period_id="control",
        prior_end=date(2021, 2, 4),
    )
    assert priors["wiki"].n == 2
    assert priors["wiki"].hi == 12.0


def test_busy_night_flags_against_quiet_prior() -> None:
    values = [10.0] * 20 + [11.0] * 10
    rows = [
        _obs("control", "wiki", date(2021, 1, 1 + index), value)
        for index, value in enumerate(values)
    ]
    prior = build_quiet_priors(
        rows,
        series_ids=["wiki"],
        control_period_id="control",
        prior_end=date(2021, 2, 4),
    )["wiki"]
    scored = score_against_prior(
        40.0,
        prior,
        threshold=2.5,
        polarity=Polarity.high_unusual,
        n_min=7,
        protocol_n_min=20,
    )
    assert scored["rhythm_state"] == "flagged"
    assert scored["rhythm_protocol_eligible"] is True
    assert float(scored["rhythm_z"] or 0) >= 2.5
    assert empirical_cdf(prior.values, 40.0) == 1.0


def test_zero_variance_quiet_prior_is_not_a_flag() -> None:
    rows = [_obs("control", "firms", date(2021, 1, 1 + index), 0.0) for index in range(30)]
    prior = build_quiet_priors(
        rows,
        series_ids=["firms"],
        control_period_id="control",
        prior_end=date(2021, 2, 4),
    )["firms"]
    scored = score_against_prior(
        0.0,
        prior,
        threshold=2.5,
        polarity=Polarity.high_unusual,
        n_min=7,
        protocol_n_min=20,
    )
    assert scored["rhythm_state"] == "insufficient_baseline"
    assert scored["rhythm_z"] is None
