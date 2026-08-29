from __future__ import annotations

import hashlib
import random
from datetime import date
from typing import Any

from wsf.features.coincidence import FlaggedSeries, alerts_from_basket_days, basket_day


def seed_for(collection_id: str, kind: str, window_id: str) -> int:
    digest = hashlib.sha256(f"{collection_id}:{kind}:{window_id}".encode()).hexdigest()
    return int(digest[:16], 16)


def chorus_counts(
    flags: list[FlaggedSeries],
    *,
    protocol: dict[str, Any],
) -> dict[str, int]:
    by_day: dict[date, list[FlaggedSeries]] = {}
    for flag in flags:
        by_day.setdefault(flag.day, []).append(flag)
    baskets = []
    for group in by_day.values():
        day = basket_day(
            group,
            k=int(protocol.get("k", 3)),
            k_costly=int(protocol.get("k_costly", 1)),
            k_domains=int(protocol.get("k_domains", 3)),
            require_distinct_families=bool(protocol.get("k_distinct_families", False)),
            require_distinct_sources=bool(protocol.get("k_distinct_source_systems", True)),
        )
        if day:
            baskets.append(day)
    alerts = alerts_from_basket_days(
        baskets, persistence_days=int(protocol.get("persistence_days", 3))
    )
    return {"n_basket_days": len(baskets), "n_episodes": len(alerts)}


def permute_independence(
    flags: list[FlaggedSeries],
    days: list[date],
    *,
    protocol: dict[str, Any],
    n_perm: int,
    seed: int,
) -> dict[str, Any]:
    """Shuffle each series' flag days independently; keep per-series flag counts.

    Null: kitchens leave their quiet band on their own calendars, no extra same-day
    coupling. Wikipedia-every-day is preserved; only alignment of the others moves.
    """
    observed = chorus_counts(flags, protocol=protocol)
    templates: dict[str, FlaggedSeries] = {}
    masks: dict[str, list[bool]] = {}
    index = {day: i for i, day in enumerate(days)}
    for flag in flags:
        templates[flag.series_id] = flag
        masks.setdefault(flag.series_id, [False] * len(days))
        if flag.day in index:
            masks[flag.series_id][index[flag.day]] = True
    rng = random.Random(seed)
    null_basket: list[int] = []
    null_episodes: list[int] = []
    for _ in range(n_perm):
        shuffled_flags: list[FlaggedSeries] = []
        for series_id, mask in masks.items():
            drawn = mask[:]
            rng.shuffle(drawn)
            proto = templates[series_id]
            for day, on in zip(days, drawn, strict=True):
                if on:
                    shuffled_flags.append(
                        FlaggedSeries(
                            period_id=proto.period_id,
                            day=day,
                            series_id=proto.series_id,
                            family=proto.family,
                            source_system=proto.source_system,
                            cost_class=proto.cost_class,
                            causal_domain=proto.causal_domain,
                        )
                    )
        counts = chorus_counts(shuffled_flags, protocol=protocol)
        null_basket.append(counts["n_basket_days"])
        null_episodes.append(counts["n_episodes"])
    return {
        "n_perm": n_perm,
        "seed": seed,
        "observed_basket_days": observed["n_basket_days"],
        "observed_episodes": observed["n_episodes"],
        "null_basket_days_mean": (sum(null_basket) / n_perm) if n_perm else None,
        "null_episodes_mean": (sum(null_episodes) / n_perm) if n_perm else None,
        "p_basket_days": _upper_p(observed["n_basket_days"], null_basket),
        "p_episodes": _upper_p(observed["n_episodes"], null_episodes),
        "note": (
            "p = (1 + #{null >= observed}) / (1 + n_perm). "
            "Independence of series flag calendars; marginal flag counts fixed."
        ),
    }


def _upper_p(observed: int, null: list[int]) -> float | None:
    if not null:
        return None
    return (1 + sum(1 for value in null if value >= observed)) / (1 + len(null))
