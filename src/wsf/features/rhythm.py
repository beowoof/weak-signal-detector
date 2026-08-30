from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date

from wsf.features.zscore import is_flagged
from wsf.types import Observation, Polarity


@dataclass(frozen=True)
class QuietPrior:
    series_id: str
    period_id: str
    prior_end: date
    n: int
    mu: float | None
    sigma: float | None
    lo: float | None
    hi: float | None
    values: tuple[float, ...]

    def summary(self) -> dict[str, object]:
        return {
            "series_id": self.series_id,
            "period_id": self.period_id,
            "prior_end": self.prior_end.isoformat(),
            "n": self.n,
            "mu": self.mu,
            "sigma": self.sigma,
            "min": self.lo,
            "max": self.hi,
        }


def build_quiet_priors(
    observations: list[Observation],
    *,
    series_ids: list[str],
    control_period_id: str,
    prior_end: date,
) -> dict[str, QuietPrior]:
    """Empirical quiet/seasonal scale: control-window values strictly before scored days."""
    priors: dict[str, QuietPrior] = {}
    for series_id in series_ids:
        values = [
            float(item.value)
            for item in observations
            if item.period_id == control_period_id
            and item.series_id == series_id
            and item.quality == "ok"
            and item.value is not None
            and item.event_time.date() < prior_end
        ]
        n = len(values)
        mu = statistics.fmean(values) if n else None
        sigma = statistics.pstdev(values) if n >= 2 else None
        priors[series_id] = QuietPrior(
            series_id=series_id,
            period_id=control_period_id,
            prior_end=prior_end,
            n=n,
            mu=mu,
            sigma=sigma,
            lo=min(values) if values else None,
            hi=max(values) if values else None,
            values=tuple(values),
        )
    return priors


def build_window_priors(
    observations: list[Observation],
    *,
    series_ids: list[str],
    period_starts: dict[str, date],
) -> dict[tuple[str, str], QuietPrior]:
    """Build a frozen, locally scaled prior before each scored window.

    Each incident and control window is normalised against its own lookback. This
    avoids interpreting secular changes in raw source volume as event rhythm.
    """
    priors: dict[tuple[str, str], QuietPrior] = {}
    for period_id, prior_end in period_starts.items():
        period_priors = build_quiet_priors(
            observations,
            series_ids=series_ids,
            control_period_id=period_id,
            prior_end=prior_end,
        )
        for series_id, prior in period_priors.items():
            priors[(period_id, series_id)] = prior
    return priors


def empirical_cdf(values: tuple[float, ...], x: float) -> float | None:
    """Return a mid-rank empirical percentile.

    Mid-ranks keep an observation equal to a constant baseline at 0.5 while a
    genuinely new value above that baseline receives 1.0.
    """
    if not values:
        return None
    below = sum(1 for value in values if value < x)
    equal = sum(1 for value in values if value == x)
    return (below + 0.5 * equal) / len(values)


def score_against_prior(
    value: float,
    prior: QuietPrior,
    *,
    threshold: float,
    polarity: Polarity,
    n_min: int,
    protocol_n_min: int,
    quantile_threshold: float = 0.99,
) -> dict[str, object]:
    rank = empirical_cdf(prior.values, value)
    payload: dict[str, object] = {
        "rhythm_n": prior.n,
        "rhythm_mu": prior.mu,
        "rhythm_sigma": prior.sigma,
        "rhythm_z": None,
        "rhythm_quantile": rank,
        "rhythm_state": "insufficient_baseline",
        "rhythm_protocol_eligible": False,
    }
    if prior.n < n_min or prior.mu is None or prior.sigma is None or rank is None:
        return payload
    payload["rhythm_protocol_eligible"] = prior.n >= protocol_n_min
    rank_flagged = _rank_flagged(rank, quantile_threshold, polarity)
    if prior.sigma == 0:
        beyond_constant = _beyond_constant(value, prior, polarity)
        payload["rhythm_state"] = "flagged" if beyond_constant and rank_flagged else "normal"
        return payload
    z = (value - prior.mu) / prior.sigma
    payload["rhythm_z"] = z
    if is_flagged(z, threshold, polarity) and rank_flagged:
        payload["rhythm_state"] = "flagged"
    else:
        payload["rhythm_state"] = "normal"
    return payload


def _rank_flagged(rank: float, threshold: float, polarity: Polarity) -> bool:
    if polarity is Polarity.high_unusual:
        return rank >= threshold
    if polarity is Polarity.low_unusual:
        return rank <= 1 - threshold
    return rank >= threshold or rank <= 1 - threshold


def _beyond_constant(value: float, prior: QuietPrior, polarity: Polarity) -> bool:
    if prior.lo is None or prior.hi is None:
        return False
    if polarity is Polarity.high_unusual:
        return value > prior.hi
    if polarity is Polarity.low_unusual:
        return value < prior.lo
    return value < prior.lo or value > prior.hi
