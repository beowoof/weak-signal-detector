"""Rolling-correlation early-warning statistics (IDEAS.md Phase 1 / Blueprint B).

This is not a retuned coincidence_v1. Marginal z-thresholds are not applied.
The question is whether the leading eigenvalue of a rolling correlation matrix
separates mobilisation windows from matched controls and hard negatives.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from wsf.connectors import SOURCE_SERIES
from wsf.scenario import load_scenario, load_status, scenario_directory
from wsf.types import Observation

# One representative per causal domain. GDELT and ICEWS share `information`;
# ICEWS is a robustness check, not a second vote. Gazette crawl counts and
# Certificate Transparency are omitted (demoted in FINDINGS.md).
DOMAIN_REPRESENTATIVES: dict[str, tuple[str, ...]] = {
    "public_attention": ("attn.wiki_pageviews",),
    "information": ("talk.gdelt_cameo",),
    "market": ("dyad.moex_usdrub", "dyad.fx"),
    "digital_infrastructure": ("net.ripe_prefixes",),
    "domestic_financial_conditions": ("market.cbr_funding_spread",),
    "spatial_restriction": ("nav.spatial_warnings",),
    "bureaucratic": ("official.gazette_cadence",),
}

CORE_DOMAINS: tuple[str, ...] = ("public_attention", "information", "market")
EXTENDED_DOMAINS: tuple[str, ...] = (
    "public_attention",
    "information",
    "market",
    "digital_infrastructure",
)
# Soft chorus plus live Option-2 costly meters, when the harvest actually has them.
COSTLY_DOMAINS: tuple[str, ...] = (
    "public_attention",
    "information",
    "market",
    "domestic_financial_conditions",
    "spatial_restriction",
    "bureaucratic",
)
OPTIONAL_DOMAINS: frozenset[str] = frozenset(
    {
        "digital_infrastructure",
        "domestic_financial_conditions",
        "spatial_restriction",
        "bureaucratic",
    }
)

TRAILING_Z_WINDOW = 90
TRAILING_Z_N_MIN = 20


@dataclass(frozen=True)
class EwsPoint:
    day: date
    n_obs: int
    n_series: int
    lambda_max: float
    mp_bound: float
    excess: float
    multi_information: float
    above_bound: bool


@dataclass
class WindowEwsSummary:
    scenario_id: str
    window_id: str
    panel: str
    series_ids: list[str]
    window_days: int
    scored_start: date
    scored_end: date
    lookback_n: int
    scored_n: int
    lookback_mean_lambda: float | None
    lookback_max_lambda: float | None
    scored_mean_lambda: float | None
    scored_max_lambda: float | None
    scored_days_above_bound: int
    delta_mean_lambda: float | None
    lookback_mean_mi: float | None
    scored_mean_mi: float | None
    permutation: dict[str, Any] = field(default_factory=dict)
    points: list[EwsPoint] = field(default_factory=list)


def marcenko_pastur_upper(n_series: int, n_obs: int) -> float:
    """Upper edge of the Marcenko-Pastur bulk for a noise correlation matrix."""
    if n_series < 2:
        raise ValueError("n_series must be at least 2")
    if n_obs < n_series:
        raise ValueError("n_obs must be at least n_series")
    ratio = n_series / n_obs
    return float((1.0 + math.sqrt(ratio)) ** 2)


def correlation_matrix(values: np.ndarray) -> np.ndarray:
    """Pearson correlation of columns. `values` is (n_obs, n_series) with no NaNs."""
    if values.ndim != 2:
        raise ValueError("values must be 2-dimensional")
    n_obs, n_series = values.shape
    if n_series < 2 or n_obs < n_series:
        raise ValueError("need n_obs >= n_series >= 2")
    if not np.isfinite(values).all():
        raise ValueError("values must be finite")
    std = values.std(axis=0, ddof=0)
    if np.any(std == 0):
        raise ValueError("constant column: correlation is undefined")
    corr = np.corrcoef(values, rowvar=False)
    corr = np.clip((corr + corr.T) / 2.0, -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    return corr


def leading_eigenvalue(corr: np.ndarray) -> float:
    eigvals = np.linalg.eigvalsh(corr)
    return float(eigvals[-1])


def multi_information(corr: np.ndarray) -> float:
    """Gaussian total correlation: I(X) = -1/2 ln det(R)."""
    sign, logdet = np.linalg.slogdet(corr)
    if sign <= 0:
        return float("inf")
    return float(-0.5 * logdet)


def trailing_z(
    values: np.ndarray,
    *,
    window: int = TRAILING_Z_WINDOW,
    n_min: int = TRAILING_Z_N_MIN,
) -> np.ndarray:
    """Population trailing z with the current point excluded from the baseline."""
    n = len(values)
    out = np.full(n, np.nan, dtype=float)
    for index in range(n):
        current = values[index]
        if not np.isfinite(current):
            continue
        start = max(0, index - window)
        baseline = values[start:index]
        baseline = baseline[np.isfinite(baseline)]
        if baseline.size < n_min:
            continue
        mu = float(baseline.mean())
        sigma = float(baseline.std(ddof=0))
        if sigma == 0:
            continue
        out[index] = (float(current) - mu) / sigma
    return out


def rolling_ews(
    z_matrix: np.ndarray,
    days: list[date],
    *,
    window: int,
    min_obs: int | None = None,
) -> list[EwsPoint]:
    """Rolling correlation λ_max and multi-information on a trailing-z panel."""
    if z_matrix.ndim != 2:
        raise ValueError("z_matrix must be 2-dimensional")
    if z_matrix.shape[0] != len(days):
        raise ValueError("z_matrix rows must match days")
    n_days, n_series = z_matrix.shape
    if n_series < 2:
        raise ValueError("need at least two series")
    required = min_obs if min_obs is not None else max(n_series, window // 2)
    points: list[EwsPoint] = []
    for end in range(n_days):
        start = max(0, end - window + 1)
        block = z_matrix[start : end + 1]
        complete = block[np.isfinite(block).all(axis=1)]
        if complete.shape[0] < required:
            continue
        try:
            corr = correlation_matrix(complete)
        except ValueError:
            continue
        lam = leading_eigenvalue(corr)
        bound = marcenko_pastur_upper(n_series, complete.shape[0])
        points.append(
            EwsPoint(
                day=days[end],
                n_obs=int(complete.shape[0]),
                n_series=n_series,
                lambda_max=lam,
                mp_bound=bound,
                excess=lam - bound,
                multi_information=multi_information(corr),
                above_bound=lam > bound,
            )
        )
    return points


def permute_delta_lambda(
    z_matrix: np.ndarray,
    days: list[date],
    *,
    window: int,
    scored_start: date,
    scored_end: date,
    observed_delta: float,
    n_perm: int,
    seed: int,
    min_obs: int | None = None,
) -> dict[str, Any]:
    """Circularly shift each series independently; test scored-minus-lookback λ_max."""
    rng = np.random.default_rng(seed)
    n_days, n_series = z_matrix.shape
    null_deltas: list[float] = []
    for _ in range(n_perm):
        perm = np.empty_like(z_matrix)
        for col in range(n_series):
            perm[:, col] = np.roll(z_matrix[:, col], int(rng.integers(0, n_days)))
        points = rolling_ews(perm, days, window=window, min_obs=min_obs)
        delta = _delta_mean_lambda(points, scored_start, scored_end)
        if delta is not None:
            null_deltas.append(delta)
    if not null_deltas:
        return {
            "n_perm": n_perm,
            "n_valid": 0,
            "observed_delta": observed_delta,
            "null_mean": None,
            "p_ge": 1.0,
        }
    null_arr = np.asarray(null_deltas, dtype=float)
    p_ge = float((np.sum(null_arr >= observed_delta) + 1) / (len(null_arr) + 1))
    return {
        "n_perm": n_perm,
        "n_valid": len(null_arr),
        "observed_delta": observed_delta,
        "null_mean": float(null_arr.mean()),
        "null_p95": float(np.quantile(null_arr, 0.95)),
        "p_ge": p_ge,
    }


def build_z_panel(
    observations: list[Observation],
    *,
    period_id: str,
    series_ids: list[str],
) -> tuple[list[date], np.ndarray]:
    """Daily trailing-z matrix for `series_ids` on `period_id`."""
    calendars = [_daily_series(observations, series_id, period_id) for series_id in series_ids]
    all_days: set[date] = set()
    for calendar in calendars:
        all_days.update(calendar)
    if not all_days:
        raise ValueError(f"no observations for {period_id}: {series_ids}")
    days = _contiguous_days(min(all_days), max(all_days))
    raw = np.full((len(days), len(series_ids)), np.nan, dtype=float)
    index = {day: i for i, day in enumerate(days)}
    for col, calendar in enumerate(calendars):
        for day, value in calendar.items():
            raw[index[day], col] = value
    z_matrix = np.column_stack([trailing_z(raw[:, col]) for col in range(raw.shape[1])])
    return days, z_matrix


def resolve_panel_series(
    observations: list[Observation],
    period_id: str,
    domains: tuple[str, ...],
) -> list[str]:
    """Pick the first representative per domain that has any ok values in-period."""
    available = {
        item.series_id
        for item in observations
        if item.period_id == period_id and item.quality == "ok" and item.value is not None
    }
    chosen: list[str] = []
    for domain in domains:
        options = DOMAIN_REPRESENTATIVES[domain]
        match = next((series_id for series_id in options if series_id in available), None)
        if match is None:
            if domain in OPTIONAL_DOMAINS:
                continue
            raise ValueError(f"{period_id}: no representative for domain {domain}")
        chosen.append(match)
    if len(chosen) < 2:
        raise ValueError(f"{period_id}: need at least two series, got {chosen}")
    return chosen


def evaluate_window_ews(
    scenario_id: str,
    window_id: str,
    observations: list[Observation],
    *,
    scored_start: date,
    scored_end: date,
    panel: str = "core",
    window: int = 14,
    run_permutation: bool = True,
    n_perm: int = 1000,
    seed: int = 42,
) -> WindowEwsSummary:
    if panel == "core":
        domains = CORE_DOMAINS
    elif panel == "costly":
        domains = COSTLY_DOMAINS
    else:
        domains = EXTENDED_DOMAINS
    series_ids = resolve_panel_series(observations, window_id, domains)
    days, z_matrix = build_z_panel(observations, period_id=window_id, series_ids=series_ids)
    points = rolling_ews(z_matrix, days, window=window)
    lookback = [p for p in points if p.day < scored_start]
    scored = [p for p in points if scored_start <= p.day <= scored_end]
    lookback_mean = _mean_lambda(lookback)
    scored_mean = _mean_lambda(scored)
    delta = None if lookback_mean is None or scored_mean is None else scored_mean - lookback_mean
    permutation: dict[str, Any] = {}
    if run_permutation and delta is not None and lookback and scored:
        permutation = permute_delta_lambda(
            z_matrix,
            days,
            window=window,
            scored_start=scored_start,
            scored_end=scored_end,
            observed_delta=delta,
            n_perm=n_perm,
            seed=seed,
        )
    return WindowEwsSummary(
        scenario_id=scenario_id,
        window_id=window_id,
        panel=panel,
        series_ids=series_ids,
        window_days=window,
        scored_start=scored_start,
        scored_end=scored_end,
        lookback_n=len(lookback),
        scored_n=len(scored),
        lookback_mean_lambda=lookback_mean,
        lookback_max_lambda=_max_lambda(lookback),
        scored_mean_lambda=scored_mean,
        scored_max_lambda=_max_lambda(scored),
        scored_days_above_bound=sum(1 for p in scored if p.above_bound),
        delta_mean_lambda=delta,
        lookback_mean_mi=_mean_mi(lookback),
        scored_mean_mi=_mean_mi(scored),
        permutation=permutation,
        points=points,
    )


def load_collection_observations(collection_dir: Path) -> list[Observation]:
    obs_dir = collection_dir / "observations"
    if not obs_dir.is_dir():
        raise FileNotFoundError(f"no observations directory: {obs_dir}")
    rows: list[Observation] = []
    for path in sorted(obs_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(Observation.model_validate_json(line))
    if not rows:
        raise ValueError(f"collection has no observations: {collection_dir}")
    return rows


def load_scenario_observations(
    project_root: Path, scenario_id: str
) -> tuple[Path, list[Observation]]:
    status = load_status(project_root, scenario_id)
    collection_id = status.get("active_collection_id")
    if not collection_id:
        raise ValueError(f"{scenario_id}: no active collection")
    collection_dir = scenario_directory(project_root, scenario_id) / "corpus" / collection_id
    rows = load_collection_observations(collection_dir)
    scenario = load_scenario(project_root, scenario_id)
    enabled_series = {
        SOURCE_SERIES[name]
        for name, cfg in scenario.sources.items()
        if cfg.enabled and name in SOURCE_SERIES
    }
    if enabled_series:
        rows = [row for row in rows if row.series_id in enabled_series]
    return collection_dir, rows


def load_window_bounds(project_root: Path, scenario_id: str) -> dict[str, tuple[date, date]]:
    scenario = load_scenario(project_root, scenario_id)
    bounds: dict[str, tuple[date, date]] = {}
    for window in (scenario.incident, *scenario.controls):
        if window.start is None or window.end is None:
            continue
        bounds[window.id] = (window.start, window.end)
    return bounds


def _daily_series(
    observations: list[Observation], series_id: str, period_id: str
) -> dict[date, float]:
    values: dict[date, float] = {}
    for item in observations:
        if item.series_id != series_id or item.period_id != period_id:
            continue
        if item.quality != "ok" or item.value is None:
            continue
        values[item.event_time.date()] = float(item.value)
    return values


def _contiguous_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _mean_lambda(points: list[EwsPoint]) -> float | None:
    if not points:
        return None
    return float(np.mean([p.lambda_max for p in points]))


def _max_lambda(points: list[EwsPoint]) -> float | None:
    if not points:
        return None
    return float(max(p.lambda_max for p in points))


def _mean_mi(points: list[EwsPoint]) -> float | None:
    finite = [p.multi_information for p in points if math.isfinite(p.multi_information)]
    if not finite:
        return None
    return float(np.mean(finite))


def _delta_mean_lambda(
    points: list[EwsPoint], scored_start: date, scored_end: date
) -> float | None:
    lookback = [p for p in points if p.day < scored_start]
    scored = [p for p in points if scored_start <= p.day <= scored_end]
    lookback_mean = _mean_lambda(lookback)
    scored_mean = _mean_lambda(scored)
    if lookback_mean is None or scored_mean is None:
        return None
    return scored_mean - lookback_mean
