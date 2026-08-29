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


def empirical_cdf(values: tuple[float, ...], x: float) -> float | None:
    if not values:
        return None
    return sum(1 for value in values if value <= x) / len(values)


def score_against_prior(
    value: float,
    prior: QuietPrior,
    *,
    threshold: float,
    polarity: Polarity,
    n_min: int,
    protocol_n_min: int,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "rhythm_n": prior.n,
        "rhythm_mu": prior.mu,
        "rhythm_sigma": prior.sigma,
        "rhythm_z": None,
        "rhythm_quantile": empirical_cdf(prior.values, value),
        "rhythm_state": "insufficient_baseline",
        "rhythm_protocol_eligible": False,
    }
    if prior.n < n_min or prior.mu is None or prior.sigma is None or prior.sigma == 0:
        return payload
    z = (value - prior.mu) / prior.sigma
    payload["rhythm_z"] = z
    payload["rhythm_protocol_eligible"] = prior.n >= protocol_n_min
    if is_flagged(z, threshold, polarity):
        payload["rhythm_state"] = "flagged"
    else:
        payload["rhythm_state"] = "normal"
    return payload
