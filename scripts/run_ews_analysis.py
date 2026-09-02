"""Phase 1 re-evaluation: rolling correlation λ_max on harvested 4-case data."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wsf.analysis.ews import (  # noqa: E402
    evaluate_window_ews,
    load_scenario_observations,
    load_window_bounds,
)

SCENARIOS = ["ukraine2022", "rus2021apr", "deu2018quiet", "usachn2018trade"]
WINDOWS = ["incident", "same-period-prior-year"]
PANELS = ["core", "costly", "extended"]
ROLLING_WINDOWS = [14, 21]
ROLES = {
    ("ukraine2022", "incident"): "Positive showcase (overt action)",
    ("ukraine2022", "same-period-prior-year"): "Matched control",
    ("rus2021apr", "incident"): "Other positive (reversed mobilisation)",
    ("rus2021apr", "same-period-prior-year"): "Matched control",
    ("deu2018quiet", "incident"): "Hard negative (quiet)",
    ("deu2018quiet", "same-period-prior-year"): "Matched control",
    ("usachn2018trade", "incident"): "Hard negative (high-tension talk)",
    ("usachn2018trade", "same-period-prior-year"): "Matched control",
}


def _fmt(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def main() -> None:
    root = Path(__file__).parent.parent
    results = []
    for scenario_id in SCENARIOS:
        _collection_dir, observations = load_scenario_observations(root, scenario_id)
        bounds = load_window_bounds(root, scenario_id)
        for window_id in WINDOWS:
            scored_start, scored_end = bounds[window_id]
            for panel in PANELS:
                for window in ROLLING_WINDOWS:
                    try:
                        result = evaluate_window_ews(
                            scenario_id,
                            window_id,
                            observations,
                            scored_start=scored_start,
                            scored_end=scored_end,
                            panel=panel,
                            window=window,
                            run_permutation=True,
                            n_perm=1000,
                            seed=42,
                        )
                    except ValueError as exc:
                        print(f"SKIP {scenario_id}/{window_id}/{panel}/W={window}: {exc}")
                        continue
                    results.append(result)

    print("=" * 128)
    print("PHASE 1: ROLLING CORRELATION λ_max (trailing-z panel, listwise complete windows)")
    print("=" * 128)
    header = (
        f"{'Scenario':<16} {'Period':<24} {'Panel':<9} {'W':>2} "
        f"{'Look λ':>8} {'Scored λ':>9} {'Δλ':>7} {'Max λ':>7} "
        f"{'>MP':>4} {'p(Δ)':>7} {'Series'}"
    )
    print(header)
    print("-" * 128)
    for result in results:
        p_ge = result.permutation.get("p_ge")
        series = ",".join(result.series_ids)
        print(
            f"{result.scenario_id:<16} {result.window_id:<24} "
            f"{result.panel:<9} {result.window_days:>2} "
            f"{_fmt(result.lookback_mean_lambda):>8} "
            f"{_fmt(result.scored_mean_lambda):>9} "
            f"{_fmt(result.delta_mean_lambda):>7} "
            f"{_fmt(result.scored_max_lambda):>7} "
            f"{result.scored_days_above_bound:>4} "
            f"{_fmt(p_ge, 3):>7} {series}"
        )
    print("=" * 128)

    lines = _markdown(results)
    out = root / "EWS_EVALUATION.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")


def _markdown(results) -> list[str]:
    primary = [
        r
        for r in results
        if r.panel == "core" and r.window_days == 14
    ]
    lines = [
        "# Phase 1: Rolling Correlation & λ_max Re-Evaluation",
        "",
        "This is the instrument specified in [`IDEAS.md`](IDEAS.md) Blueprint B / Phase 1: "
        "trailing-z series, rolling Pearson correlation, leading eigenvalue versus the "
        "Marcenko-Pastur bulk edge, and Gaussian multi-information. "
        "It is **not** a retune of `coincidence_v1`. The lowered-threshold domain-count "
        "experiment in [`COUPLING_EVALUATION.md`](COUPLING_EVALUATION.md) remains a "
        "marginal-exceedance detector and is reported separately.",
        "",
        "Panel: one representative per causal domain "
        "(`attn.wiki_pageviews`, `talk.gdelt_cameo`, market = `dyad.moex_usdrub` or `dyad.fx`). "
        "ICEWS is omitted from the matrix because it shares the information domain with GDELT. "
        "Gazette crawl counts and Certificate Transparency are omitted (demoted in "
        "[`FINDINGS.md`](FINDINGS.md)). RIPEstat is a sensitivity panel only.",
        "",
        "Statistic: mean λ_max in the 21-day scored window minus mean λ_max in that "
        "window's own lookback. Permutation: independent circular shifts of each series, "
        "p = P(Δλ_null ≥ Δλ_obs).",
        "",
        "---",
        "",
        "## 1. Core panel, W = 14",
        "",
        "| Scenario | Period | Role | Series | Lookback mean "
        "λ_max | Scored mean λ_max | Δλ_max | Scored max λ_max | "
        "Days λ_max > MP | p(Δλ) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in primary:
        role = ROLES.get((result.scenario_id, result.window_id), "")
        p_ge = result.permutation.get("p_ge")
        lines.append(
            f"| `{result.scenario_id}` | `{result.window_id}` | {role} | "
            f"{', '.join(f'`{s}`' for s in result.series_ids)} | "
            f"{_fmt(result.lookback_mean_lambda)} | {_fmt(result.scored_mean_lambda)} | "
            f"{_fmt(result.delta_mean_lambda)} | {_fmt(result.scored_max_lambda)} | "
            f"{result.scored_days_above_bound}/{result.scored_n} | {_fmt(p_ge, 3)} |"
        )

    ukraine_daily = next(
        (
            r
            for r in results
            if r.scenario_id == "ukraine2022"
            and r.window_id == "incident"
            and r.panel == "core"
            and r.window_days == 14
        ),
        None,
    )
    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Reading the table",
            "",
            *_reading(primary),
            "",
        ]
    )
    if ukraine_daily is not None:
        lines.extend(
            [
                "### Ukraine 2022 incident, daily λ_max (core, W = 14)",
                "",
                "| Day | λ_max | excess vs MP | above bound |",
                "|---|---|---|---|",
            ]
        )
        for point in ukraine_daily.points:
            if ukraine_daily.scored_start <= point.day <= ukraine_daily.scored_end:
                flag = "yes" if point.above_bound else "no"
                lines.append(
                    f"| {point.day.isoformat()} | {point.lambda_max:.3f} | "
                    f"{point.excess:+.3f} | {flag} |"
                )
        lines.append("")
    lines.extend(
        [
            "---",
            "",
            "## 3. Sensitivity: W = 21 and RIPEstat-extended panel",
            "",
            "| Scenario | Period | Panel | W | Δλ_max | p(Δλ) | Days > MP |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for result in results:
        if result.panel == "core" and result.window_days == 14:
            continue
        p_ge = result.permutation.get("p_ge")
        lines.append(
            f"| `{result.scenario_id}` | `{result.window_id}` | `{result.panel}` | "
            f"{result.window_days} | {_fmt(result.delta_mean_lambda)} | {_fmt(p_ge, 3)} | "
            f"{result.scored_days_above_bound}/{result.scored_n} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. What this does and does not claim",
            "",
            "- This is a **development-set** re-analysis of the same four harvested cases. "
            "It is not a freeze and not a hold-out.",
            "- λ_max measures **fluctuation dependence** inside a rolling window. "
            "Simultaneous level shifts that then sit still can look weakly correlated "
            "after demeaning; that is a known limit of correlation-based EWS.",
            "- FINDINGS.md already noted that RIPEstat's February prefix collapse is more "
            "likely a coverage hole than a routing event. The extended panel is therefore "
            "a sensitivity, not a confirmation source.",
            "- A significant Δλ_max on Ukraine and rus2021apr with quiet hard negatives "
            "would support salvaging the *dependence* form of the thesis. "
            "A non-separation would mean Phase 1 does not rescue the instrument, "
            "and the remaining salvage routes are new costly series (Blueprint A) "
            "or spatial re-aggregation (Blueprint C), not another threshold tweak.",
            "",
        ]
    )
    return lines


def _reading(primary) -> list[str]:
    by_key = {(r.scenario_id, r.window_id): r for r in primary}
    ukraine = by_key.get(("ukraine2022", "incident"))
    rus = by_key.get(("rus2021apr", "incident"))
    deu = by_key.get(("deu2018quiet", "incident"))
    trade = by_key.get(("usachn2018trade", "incident"))
    controls = [
        by_key.get((s, "same-period-prior-year"))
        for s in SCENARIOS
    ]

    def _sig(result) -> bool:
        if result is None or result.delta_mean_lambda is None:
            return False
        p_ge = result.permutation.get("p_ge")
        return result.delta_mean_lambda > 0 and p_ge is not None and p_ge < 0.05

    positives_fire = _sig(ukraine) and _sig(rus)
    def _quiet(result) -> bool:
        if result is None or result.delta_mean_lambda is None:
            return True
        p_ge = result.permutation.get("p_ge", 1)
        return result.delta_mean_lambda <= 0 or p_ge >= 0.05

    negatives_quiet = all(_quiet(r) for r in (deu, trade))
    controls_quiet = all(_quiet(r) for r in controls if r is not None)

    bullets = []
    if positives_fire and negatives_quiet and controls_quiet:
        bullets.append(
            "- **Separation:** both mobilisation windows show a lookback-relative rise in "
            "λ_max that is unusual under independent circular shifts, while quiet, "
            "high-tension-talk, and prior-year controls do not. That is the Phase 1 "
            "result the salvage plan asked for — still development-set only."
        )
    elif positives_fire and not negatives_quiet:
        bullets.append(
            "- **Partial:** mobilisation windows rise, but at least one hard negative "
            "also produces a comparable Δλ_max. Dependence is not specific to costly "
            "preparation on this basket."
        )
    elif not positives_fire:
        bullets.append(
            "- **No salvage on this instrument:** the 21-day mobilisation windows do not "
            "show a statistically unusual rise in rolling λ_max relative to their own "
            "lookback after independent phase randomisation. Lowering z-thresholds in "
            "the coincidence detector is not a substitute for this result."
        )
    else:
        bullets.append(
            "- **Mixed:** inspect the table. The permutation p-values are the claim, "
            "not the raw λ_max levels (which can sit above the Marcenko-Pastur edge "
            "whenever any two series are modestly correlated)."
        )

    if ukraine is not None:
        bullets.append(
            f"- `ukraine2022` incident: Δλ_max = {_fmt(ukraine.delta_mean_lambda)}, "
            f"p = {_fmt(ukraine.permutation.get('p_ge'), 3)}, "
            f"scored mean λ_max = {_fmt(ukraine.scored_mean_lambda)} vs lookback "
            f"{_fmt(ukraine.lookback_mean_lambda)}."
        )
    if rus is not None:
        bullets.append(
            f"- `rus2021apr` incident: Δλ_max = {_fmt(rus.delta_mean_lambda)}, "
            f"p = {_fmt(rus.permutation.get('p_ge'), 3)}."
        )
    if deu is not None:
        bullets.append(
            f"- `deu2018quiet` incident: Δλ_max = {_fmt(deu.delta_mean_lambda)}, "
            f"p = {_fmt(deu.permutation.get('p_ge'), 3)}."
        )
    if trade is not None:
        bullets.append(
            f"- `usachn2018trade` incident: Δλ_max = {_fmt(trade.delta_mean_lambda)}, "
            f"p = {_fmt(trade.permutation.get('p_ge'), 3)}."
        )
    return bullets


if __name__ == "__main__":
    main()
