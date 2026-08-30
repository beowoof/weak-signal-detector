from __future__ import annotations

import hashlib
import random
import statistics
from collections.abc import Iterable
from datetime import date, timedelta
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
    available_days: dict[str, list[date]] | None = None,
) -> dict[str, Any]:
    """Circularly shift each flag calendar over that series' available days.

    Null: each kitchen preserves its flag count, run structure, and observability
    mask, but its phase is independent of the other kitchens.
    """
    observed = chorus_counts(flags, protocol=protocol)
    templates: dict[str, FlaggedSeries] = {}
    masks: dict[str, list[bool]] = {}
    calendars: dict[str, list[date]] = {}
    for flag in flags:
        templates[flag.series_id] = flag
    for series_id in templates:
        calendar = sorted(set((available_days or {}).get(series_id, days)))
        calendars[series_id] = calendar
        flagged_days = {flag.day for flag in flags if flag.series_id == series_id}
        masks[series_id] = [day in flagged_days for day in calendar]
    rng = random.Random(seed)
    null_basket: list[int] = []
    null_episodes: list[int] = []
    for _ in range(n_perm):
        shuffled_flags: list[FlaggedSeries] = []
        for series_id, mask in masks.items():
            if not mask:
                continue
            offset = rng.randrange(len(mask))
            drawn = mask[-offset:] + mask[:-offset] if offset else mask[:]
            proto = templates[series_id]
            for day, on in zip(calendars[series_id], drawn, strict=True):
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
    basket_mean = (sum(null_basket) / n_perm) if n_perm else None
    episode_mean = (sum(null_episodes) / n_perm) if n_perm else None
    return {
        "n_perm": n_perm,
        "seed": seed,
        "observed_basket_days": observed["n_basket_days"],
        "observed_episodes": observed["n_episodes"],
        "null_basket_days_mean": basket_mean,
        "null_basket_days_sd": statistics.pstdev(null_basket) if null_basket else None,
        "null_episodes_mean": episode_mean,
        "null_episodes_sd": statistics.pstdev(null_episodes) if null_episodes else None,
        "basket_days_effect": observed["n_basket_days"] - basket_mean
        if basket_mean is not None
        else None,
        "episodes_effect": observed["n_episodes"] - episode_mean
        if episode_mean is not None
        else None,
        "p_basket_days": _upper_p(observed["n_basket_days"], null_basket),
        "p_episodes": _upper_p(observed["n_episodes"], null_episodes),
        "basket_days_null_percentile": _lower_percentile(observed["n_basket_days"], null_basket),
        "episodes_null_percentile": _lower_percentile(observed["n_episodes"], null_episodes),
        "available_day_counts": {
            series_id: len(calendar) for series_id, calendar in calendars.items()
        },
        "method": "independent_circular_shift_within_available_days",
        "note": (
            "p = (1 + #{null >= observed}) / (1 + n_perm). "
            "Independent circular shifts preserve flag runs and per-series availability."
        ),
    }


def amber_days(
    flags: list[FlaggedSeries],
    days: list[date],
    *,
    costly_unknown_days: Iterable[date],
    costly_flagged_days: Iterable[date] | None = None,
    min_flags: int = 2,
    min_domains: int = 2,
) -> set[date]:
    """Days with ≥2 non-costly domains flagged while costly evidence stays unknown."""
    unknown = set(costly_unknown_days)
    costly_flagged = set(costly_flagged_days or ())
    by_day: dict[date, list[FlaggedSeries]] = {}
    for flag in flags:
        by_day.setdefault(flag.day, []).append(flag)
    marked: set[date] = set()
    for day in days:
        if day not in unknown or day in costly_flagged:
            continue
        unique = {item.series_id: item for item in by_day.get(day, [])}
        if len(unique) < min_flags:
            continue
        if len({item.causal_domain for item in unique.values()}) < min_domains:
            continue
        marked.add(day)
    return marked


def max_run_length(days: list[date], marked: Iterable[date]) -> int:
    """Longest consecutive calendar-day run inside `days` that is also marked."""
    marked_set = set(marked)
    best = 0
    current = 0
    previous: date | None = None
    for day in sorted(days):
        if (
            day in marked_set
            and previous is not None
            and day == previous + timedelta(days=1)
            and current
        ):
            current += 1
        elif day in marked_set:
            current = 1
        else:
            current = 0
        if current > best:
            best = current
        previous = day
    return best


def count_runs_at_least(days: list[date], marked: Iterable[date], persistence: int) -> int:
    marked_set = set(marked)
    n_runs = 0
    current = 0
    previous: date | None = None
    for day in sorted(days):
        on = day in marked_set
        consecutive = previous is not None and day == previous + timedelta(days=1)
        if on and consecutive and current:
            current += 1
        elif on:
            if current >= persistence:
                n_runs += 1
            current = 1
        else:
            if current >= persistence:
                n_runs += 1
            current = 0
        previous = day
    if current >= persistence:
        n_runs += 1
    return n_runs


def permute_amber(
    flags: list[FlaggedSeries],
    days: list[date],
    *,
    protocol: dict[str, Any],
    n_perm: int,
    seed: int,
    available_days: dict[str, list[date]] | None = None,
    costly_unknown_days: Iterable[date],
    costly_flagged_days: Iterable[date] | None = None,
) -> dict[str, Any]:
    """Shift non-costly flag calendars; keep the costly/VIIRS unknown mask fixed.

    Null: each non-costly kitchen keeps its flag count, run structure, and
    observability mask, but its phase is independent of the other kitchens and
    of the cloudy/unknown costly nights. Statistic: maximum consecutive amber
    run. p = P(null max_run ≥ observed).
    """
    unknown = set(costly_unknown_days)
    costly_flagged = set(costly_flagged_days or ())
    persistence = int(protocol.get("amber_persistence_days", protocol.get("persistence_days", 3)))
    observed_days = amber_days(
        flags,
        days,
        costly_unknown_days=unknown,
        costly_flagged_days=costly_flagged,
    )
    observed_max_run = max_run_length(days, observed_days)
    observed_episodes = count_runs_at_least(days, observed_days, persistence)
    templates: dict[str, FlaggedSeries] = {}
    masks: dict[str, list[bool]] = {}
    calendars: dict[str, list[date]] = {}
    for flag in flags:
        templates[flag.series_id] = flag
    for series_id in templates:
        calendar = sorted(set((available_days or {}).get(series_id, days)))
        calendars[series_id] = calendar
        flagged_days = {flag.day for flag in flags if flag.series_id == series_id}
        masks[series_id] = [day in flagged_days for day in calendar]
    rng = random.Random(seed)
    null_max_run: list[int] = []
    null_episodes: list[int] = []
    null_amber_days: list[int] = []
    for _ in range(n_perm):
        shuffled_flags: list[FlaggedSeries] = []
        for series_id, mask in masks.items():
            if not mask:
                continue
            offset = rng.randrange(len(mask))
            drawn = mask[-offset:] + mask[:-offset] if offset else mask[:]
            proto = templates[series_id]
            for day, on in zip(calendars[series_id], drawn, strict=True):
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
        drawn_days = amber_days(
            shuffled_flags,
            days,
            costly_unknown_days=unknown,
            costly_flagged_days=costly_flagged,
        )
        null_amber_days.append(len(drawn_days))
        null_max_run.append(max_run_length(days, drawn_days))
        null_episodes.append(count_runs_at_least(days, drawn_days, persistence))
    max_run_mean = (sum(null_max_run) / n_perm) if n_perm else None
    episode_mean = (sum(null_episodes) / n_perm) if n_perm else None
    amber_day_mean = (sum(null_amber_days) / n_perm) if n_perm else None
    return {
        "n_perm": n_perm,
        "seed": seed,
        "observed_max_run": observed_max_run,
        "observed_amber_days": len(observed_days),
        "observed_episodes": observed_episodes,
        "null_max_run_mean": max_run_mean,
        "null_max_run_sd": statistics.pstdev(null_max_run) if null_max_run else None,
        "null_amber_days_mean": amber_day_mean,
        "null_episodes_mean": episode_mean,
        "null_episodes_sd": statistics.pstdev(null_episodes) if null_episodes else None,
        "max_run_effect": observed_max_run - max_run_mean if max_run_mean is not None else None,
        "episodes_effect": observed_episodes - episode_mean if episode_mean is not None else None,
        "p_max_run": _upper_p(observed_max_run, null_max_run),
        "p_episodes": _upper_p(observed_episodes, null_episodes),
        "frozen_costly_unknown_days": len(unknown),
        "frozen_costly_flagged_days": len(costly_flagged),
        "available_day_counts": {
            series_id: len(calendar) for series_id, calendar in calendars.items()
        },
        "method": "independent_circular_shift_soft_flags_frozen_costly_mask",
        "statistic": "max_run_length",
        "note": (
            "p_max_run = (1 + #{null max_run >= observed}) / (1 + n_perm). "
            "Non-costly flag calendars are circularly shifted; the costly/VIIRS "
            "unknown mask is held fixed."
        ),
    }


def _upper_p(observed: int, null: list[int]) -> float | None:
    if not null:
        return None
    return (1 + sum(1 for value in null if value >= observed)) / (1 + len(null))


def _lower_percentile(observed: int, null: list[int]) -> float | None:
    if not null:
        return None
    return (1 + sum(1 for value in null if value <= observed)) / (1 + len(null))
