from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from wsf.analysis.ews import (
    correlation_matrix,
    evaluate_window_ews,
    leading_eigenvalue,
    marcenko_pastur_upper,
    multi_information,
    resolve_panel_series,
    rolling_ews,
    trailing_z,
)
from wsf.types import Observation


def test_marcenko_pastur_upper_matches_closed_form() -> None:
    expected = (1.0 + np.sqrt(4 / 14)) ** 2
    assert marcenko_pastur_upper(4, 14) == pytest.approx(float(expected))


def test_identity_has_unit_eigenvalue_and_zero_multi_information() -> None:
    corr = np.eye(3)
    assert leading_eigenvalue(corr) == pytest.approx(1.0)
    assert multi_information(corr) == pytest.approx(0.0)


def test_perfectly_coupled_columns_saturate_lambda_max() -> None:
    rng = np.random.default_rng(0)
    signal = rng.standard_normal(80)
    values = np.column_stack([signal, signal * 2 + 1.0, -signal])
    lam = leading_eigenvalue(correlation_matrix(values))
    assert lam == pytest.approx(3.0, abs=1e-8)
    assert multi_information(correlation_matrix(values)) == float("inf")


def test_equicorrelated_gaussians_recover_population_lambda() -> None:
    rng = np.random.default_rng(1)
    n_series = 4
    rho = 0.5
    true = np.full((n_series, n_series), rho)
    np.fill_diagonal(true, 1.0)
    factor = np.linalg.cholesky(true)
    sample = rng.standard_normal((20_000, n_series)) @ factor.T
    lam = leading_eigenvalue(correlation_matrix(sample))
    assert lam == pytest.approx(1.0 + (n_series - 1) * rho, abs=0.05)


def test_independent_gaussians_stay_near_marcenko_pastur_edge() -> None:
    rng = np.random.default_rng(2)
    n_obs, n_series = 5_000, 4
    sample = rng.standard_normal((n_obs, n_series))
    lam = leading_eigenvalue(correlation_matrix(sample))
    bound = marcenko_pastur_upper(n_series, n_obs)
    assert lam < bound + 0.05


def test_trailing_z_excludes_current_and_matches_population_sigma() -> None:
    values = np.array([0.0, 2.0] * 10 + [5.0])
    scored = trailing_z(values, window=90, n_min=20)
    assert np.isnan(scored[:20]).all()
    mu = 1.0
    sigma = float(np.array([0.0, 2.0] * 10).std(ddof=0))
    assert scored[20] == pytest.approx((5.0 - mu) / sigma)


def test_rolling_ews_detects_a_late_shared_shock() -> None:
    rng = np.random.default_rng(3)
    n_days = 80
    days = [date(2022, 1, 1) + timedelta(days=offset) for offset in range(n_days)]
    independent = rng.standard_normal((n_days, 3))
    coupled = independent.copy()
    shock = np.zeros(n_days)
    shock[-14:] = rng.standard_normal(14) * 4.0
    coupled[-14:] += shock[-14:, None]
    quiet = rolling_ews(independent, days, window=14, min_obs=10)
    loud = rolling_ews(coupled, days, window=14, min_obs=10)
    quiet_tail = np.mean([p.lambda_max for p in quiet if p.day >= days[-14]])
    loud_tail = np.mean([p.lambda_max for p in loud if p.day >= days[-14]])
    assert loud_tail > quiet_tail + 0.3


def _obs(series_id: str, period_id: str, day: date, value: float) -> Observation:
    moment = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return Observation(
        version_id=f"{series_id}:{day.isoformat()}",
        series_id=series_id,
        period_id=period_id,
        event_time=moment,
        available_at=moment,
        retrieved_at=datetime(2026, 8, 28, tzinfo=UTC),
        value=value,
        quality="ok",
    )


def test_evaluate_window_ews_rises_only_in_the_scored_window() -> None:
    rng = np.random.default_rng(4)
    start = date(2021, 10, 1)
    scored_start = date(2022, 2, 3)
    scored_end = date(2022, 2, 23)
    n_days = (scored_end - start).days + 1
    days = [start + timedelta(days=offset) for offset in range(n_days)]
    wiki = rng.standard_normal(n_days)
    gdelt = rng.standard_normal(n_days)
    market = rng.standard_normal(n_days)
    for index, day in enumerate(days):
        if scored_start <= day <= scored_end:
            shared = 3.0 + 0.2 * (index % 5)
            wiki[index] += shared
            gdelt[index] += shared
            market[index] += shared
    observations = []
    for index, day in enumerate(days):
        observations.extend(
            [
                _obs("attn.wiki_pageviews", "incident", day, float(wiki[index])),
                _obs("talk.gdelt_cameo", "incident", day, float(gdelt[index])),
                _obs("dyad.moex_usdrub", "incident", day, float(market[index])),
            ]
        )
    result = evaluate_window_ews(
        "fixture",
        "incident",
        observations,
        scored_start=scored_start,
        scored_end=scored_end,
        panel="core",
        window=14,
        run_permutation=True,
        n_perm=200,
        seed=7,
    )
    assert result.scored_mean_lambda is not None
    assert result.lookback_mean_lambda is not None
    assert result.delta_mean_lambda is not None
    assert result.delta_mean_lambda > 0.2
    assert result.permutation["p_ge"] < 0.05


def test_costly_panel_skips_missing_optional_domains() -> None:
    start = date(2022, 1, 1)
    observations = [
        _obs("attn.wiki_pageviews", "incident", start, 1.0),
        _obs("talk.gdelt_cameo", "incident", start, 2.0),
        _obs("dyad.moex_usdrub", "incident", start, 3.0),
        _obs("market.cbr_funding_spread", "incident", start, -12.0),
        _obs("nav.spatial_warnings", "incident", start, 4.0),
    ]
    series = resolve_panel_series(
        observations,
        "incident",
        (
            "public_attention",
            "information",
            "market",
            "domestic_financial_conditions",
            "spatial_restriction",
            "bureaucratic",
        ),
    )
    assert series == [
        "attn.wiki_pageviews",
        "talk.gdelt_cameo",
        "dyad.moex_usdrub",
        "market.cbr_funding_spread",
        "nav.spatial_warnings",
    ]
