# Phase 1: Rolling Correlation & λ_max Re-Evaluation

**Verdict:** Phase 1 does not salvage the instrument. Rolling λ_max rises in the Ukraine 2022 scored window (Δ = 0.30, p = 0.067) and stays quiet on both hard negatives, but April 2021 does not rise, and Ukraine itself is only a one-sided near-miss under independent circular shifts. That is the same epistemic neighbourhood as [`FINDINGS.md`](FINDINGS.md): something in the public series is different in February 2022; this basket still cannot say it is strategic coupling.

This is the instrument specified in [`IDEAS.md`](IDEAS.md) Blueprint B / Phase 1: trailing-z series, rolling Pearson correlation, leading eigenvalue versus the Marcenko-Pastur bulk edge, and Gaussian multi-information. It is **not** a retune of `coincidence_v1`. The lowered-threshold domain-count experiment in [`COUPLING_EVALUATION.md`](COUPLING_EVALUATION.md) remains a marginal-exceedance detector.

---

## 0. What was measured

- **Panel:** one representative per causal domain — Wikipedia pageviews, GDELT CAMEO, market (`dyad.moex_usdrub` or `dyad.fx`). ICEWS is omitted because it shares the information domain with GDELT. Gazette crawl counts and Certificate Transparency are omitted (demoted in FINDINGS.md). RIPEstat is a sensitivity panel only.
- **Standardisation:** population trailing z, 90-day window, current day excluded, `n_min = 20`, matching `coincidence_v1`.
- **Rolling window:** W = 14 calendar days, listwise complete rows (so market weekends drop out; typically n_obs = 10 for M = 3). W = 21 is a sensitivity.
- **Test statistic:** mean λ_max in the 21-day scored window minus mean λ_max in that window's own lookback. Permutation: independent circular shifts of each series, 1000 draws, p = P(Δλ_null ≥ Δλ_obs).
- **Development set only.** Same four harvested cases. Not a freeze. Not a hold-out.

For M = 3, n_obs = 10 the Marcenko-Pastur upper edge is (1 + √(3/10))² ≈ 2.40. λ_max sitting near 2 is ordinary pairwise correlation, not a collapsed-independence event.

---

## 1. Core panel, W = 14

| Scenario | Period | Role | Series | Lookback mean λ_max | Scored mean λ_max | Δλ_max | Scored max λ_max | Days λ_max > MP | p(Δλ) |
|---|---|---|---|---|---|---|---|---|---|
| `ukraine2022` | `incident` | Positive showcase (overt action) | `attn.wiki_pageviews`, `talk.gdelt_cameo`, `dyad.moex_usdrub` | 1.940 | 2.239 | 0.299 | 2.539 | 5/21 | 0.067 |
| `ukraine2022` | `same-period-prior-year` | Matched control | `attn.wiki_pageviews`, `talk.gdelt_cameo`, `dyad.moex_usdrub` | 1.725 | 1.727 | 0.002 | 2.457 | 1/21 | 0.520 |
| `rus2021apr` | `incident` | Other positive (reversed mobilisation) | `attn.wiki_pageviews`, `talk.gdelt_cameo`, `dyad.moex_usdrub` | 1.675 | 1.810 | 0.135 | 2.619 | 2/21 | 0.276 |
| `rus2021apr` | `same-period-prior-year` | Matched control | `attn.wiki_pageviews`, `talk.gdelt_cameo`, `dyad.moex_usdrub` | 1.711 | 1.773 | 0.063 | 1.923 | 0/21 | 0.362 |
| `deu2018quiet` | `incident` | Hard negative (quiet) | `attn.wiki_pageviews`, `talk.gdelt_cameo`, `dyad.fx` | 1.761 | 1.418 | -0.343 | 1.675 | 0/17 | 0.973 |
| `deu2018quiet` | `same-period-prior-year` | Matched control | `attn.wiki_pageviews`, `talk.gdelt_cameo`, `dyad.fx` | 1.695 | 1.657 | -0.038 | 2.161 | 0/17 | 0.550 |
| `usachn2018trade` | `incident` | Hard negative (high-tension talk) | `attn.wiki_pageviews`, `talk.gdelt_cameo`, `dyad.fx` | 1.624 | 1.671 | 0.046 | 1.849 | 0/17 | 0.398 |
| `usachn2018trade` | `same-period-prior-year` | Matched control | `attn.wiki_pageviews`, `talk.gdelt_cameo`, `dyad.fx` | 1.558 | 1.732 | 0.173 | 2.030 | 0/17 | 0.209 |

DEU and USA–China scored n < 21 because ALFRED H.10 FX is missing on the last days of the window (print lag), so those days have no complete market row.

---

## 2. Reading

- **Ukraine 2022 is a near-miss, not a detection.** Mean λ_max rises from 1.94 in lookback to 2.24 in the scored window. Independent phase randomisation puts that Δ at p = 0.067. Lookback already reached 2.45; scored max is 2.54. The first principal component is a bit louder, not a new regime.
- **April 2021 is a miss.** Δ = 0.14, p = 0.28 at W = 14; at W = 21 the scored window is *less* coupled than its lookback (Δ = −0.11). The reversed mobilisation does not show a collapse of independence on this basket. Capital-postage-stamp physical series were already a miss in FINDINGS.md; the soft-series correlation matrix does not recover it.
- **Hard negatives behave.** Germany 2018 decoupling (Δ = −0.34, p = 0.97). USA–China tariff week is flat (Δ = 0.05, p = 0.40). Prior-year controls are flat. Specificity is the one clean result.
- **W = 21 and RIPEstat do not rescue it.** Ukraine W = 21 core: Δ = 0.34, p = 0.059. Adding RIPEstat *weakens* Ukraine (p = 0.18 at W = 14) and does nothing for April 2021. FINDINGS.md already treated the February prefix collapse as a likely hole.

### Ukraine 2022 incident, daily λ_max (core, W = 14)

| Day | λ_max | excess vs MP | above bound |
|---|---|---|---|
| 2022-02-03 | 2.307 | −0.088 | no |
| 2022-02-04 | 2.471 | +0.075 | yes |
| 2022-02-05 | 2.471 | +0.075 | yes |
| 2022-02-06 | 2.471 | +0.075 | yes |
| 2022-02-07 | 2.359 | −0.037 | no |
| 2022-02-08 | 2.539 | +0.143 | yes |
| 2022-02-09 | 2.331 | −0.064 | no |
| 2022-02-10 | 2.025 | −0.370 | no |
| 2022-02-11 | 2.074 | −0.321 | no |
| 2022-02-12 | 2.074 | −0.321 | no |
| 2022-02-13 | 2.074 | −0.321 | no |
| 2022-02-14 | 2.304 | −0.091 | no |
| 2022-02-15 | 1.971 | −0.425 | no |
| 2022-02-16 | 1.958 | −0.438 | no |
| 2022-02-17 | 2.056 | −0.339 | no |
| 2022-02-18 | 2.105 | −0.291 | no |
| 2022-02-19 | 2.105 | −0.291 | no |
| 2022-02-20 | 2.105 | −0.291 | no |
| 2022-02-21 | 2.379 | −0.016 | no |
| 2022-02-22 | 2.464 | +0.069 | yes |
| 2022-02-23 | 2.369 | −0.026 | no |

The loudest coupling is **4–8 February**, not 21–23 February. The 15 February talk/attention cluster that FINDINGS.md flagged is a λ_max *trough* (1.97): the series are simultaneously elevated, so the rolling correlation demeans them into a plateau. That is the known limit of correlation-based EWS. Coincidence of high z and collapse of independence are different hypotheses; this window illustrates both, on different days.

---

## 3. Sensitivity: W = 21 and RIPEstat-extended panel

| Scenario | Period | Panel | W | Δλ_max | p(Δλ) | Days > MP |
|---|---|---|---|---|---|---|
| `ukraine2022` | `incident` | `core` | 21 | 0.337 | 0.059 | 16/21 |
| `ukraine2022` | `incident` | `extended` | 14 | 0.237 | 0.184 | 7/21 |
| `ukraine2022` | `incident` | `extended` | 21 | 0.396 | 0.102 | 15/21 |
| `ukraine2022` | `same-period-prior-year` | `core` | 21 | 0.227 | 0.178 | 8/21 |
| `ukraine2022` | `same-period-prior-year` | `extended` | 14 | -0.163 | 0.747 | 0/21 |
| `ukraine2022` | `same-period-prior-year` | `extended` | 21 | 0.173 | 0.244 | 6/21 |
| `rus2021apr` | `incident` | `core` | 21 | -0.114 | 0.715 | 0/21 |
| `rus2021apr` | `incident` | `extended` | 14 | 0.009 | 0.514 | 1/21 |
| `rus2021apr` | `incident` | `extended` | 21 | -0.158 | 0.778 | 0/21 |
| `rus2021apr` | `same-period-prior-year` | `core` | 21 | -0.040 | 0.523 | 0/21 |
| `rus2021apr` | `same-period-prior-year` | `extended` | 14 | 0.196 | 0.230 | 0/21 |
| `rus2021apr` | `same-period-prior-year` | `extended` | 21 | 0.169 | 0.240 | 5/21 |
| `deu2018quiet` | `incident` | `core` | 21 | -0.285 | 0.933 | 0/18 |
| `deu2018quiet` | `incident` | `extended` | 14 | -0.332 | 0.920 | 0/17 |
| `deu2018quiet` | `incident` | `extended` | 21 | -0.355 | 0.933 | 0/18 |
| `deu2018quiet` | `same-period-prior-year` | `core` | 21 | 0.091 | 0.298 | 4/18 |
| `deu2018quiet` | `same-period-prior-year` | `extended` | 14 | 0.153 | 0.251 | 1/17 |
| `deu2018quiet` | `same-period-prior-year` | `extended` | 21 | 0.332 | 0.083 | 7/18 |
| `usachn2018trade` | `incident` | `core` | 21 | 0.097 | 0.303 | 0/21 |
| `usachn2018trade` | `incident` | `extended` | 14 | 0.201 | 0.182 | 0/17 |
| `usachn2018trade` | `incident` | `extended` | 21 | 0.277 | 0.168 | 0/21 |
| `usachn2018trade` | `same-period-prior-year` | `core` | 21 | 0.006 | 0.484 | 0/21 |
| `usachn2018trade` | `same-period-prior-year` | `extended` | 14 | -0.023 | 0.531 | 0/17 |
| `usachn2018trade` | `same-period-prior-year` | `extended` | 21 | -0.203 | 0.807 | 0/21 |

Germany's prior-year extended W = 21 (p = 0.083) is a reminder that RIPEstat can manufacture a Δ on a quiet control.

---

## 4. What this does and does not claim

- Development-set re-analysis of the same four harvested cases. Not a freeze. Not a hold-out. Do not score `GRC-TUR-2020` as if one existed.
- λ_max measures **fluctuation dependence** inside a rolling window. Simultaneous level shifts that then sit still look weakly correlated after demeaning (see 15 February above). Coincidence of high z is a different statistic; lowering τ does not become λ_max.
- A significant Δλ_max on Ukraine *and* rus2021apr, with quiet hard negatives, would have supported salvaging the dependence form of the thesis. That did not happen.
- Remaining salvage routes in IDEAS.md, if any, are **Blueprint A** (non-optical costly series: NOTAMs, gazette gaps, money-market basis) and **Blueprint C** (frontier corridor aggregation). They require new harvests. They are not another pass over these z-calendars.
