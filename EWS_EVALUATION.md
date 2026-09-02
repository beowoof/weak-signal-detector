# Phase 1: Rolling Correlation & λ_max Re-Evaluation

This is the instrument specified in [`IDEAS.md`](IDEAS.md) Blueprint B / Phase 1: trailing-z series, rolling Pearson correlation, leading eigenvalue versus the Marcenko-Pastur bulk edge, and Gaussian multi-information. It is **not** a retune of `coincidence_v1`. The lowered-threshold domain-count experiment in [`COUPLING_EVALUATION.md`](COUPLING_EVALUATION.md) remains a marginal-exceedance detector and is reported separately.

Panel: one representative per causal domain (`attn.wiki_pageviews`, `talk.gdelt_cameo`, market = `dyad.moex_usdrub` or `dyad.fx`). ICEWS is omitted from the matrix because it shares the information domain with GDELT. Gazette crawl counts and Certificate Transparency are omitted (demoted in [`FINDINGS.md`](FINDINGS.md)). RIPEstat is a sensitivity panel only.

Statistic: mean λ_max in the 21-day scored window minus mean λ_max in that window's own lookback. Permutation: independent circular shifts of each series, p = P(Δλ_null ≥ Δλ_obs).

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

---

## 2. Reading the table

- **No salvage on this instrument:** the 21-day mobilisation windows do not show a statistically unusual rise in rolling λ_max relative to their own lookback after independent phase randomisation. Lowering z-thresholds in the coincidence detector is not a substitute for this result.
- `ukraine2022` incident: Δλ_max = 0.299, p = 0.067, scored mean λ_max = 2.239 vs lookback 1.940.
- `rus2021apr` incident: Δλ_max = 0.135, p = 0.276.
- `deu2018quiet` incident: Δλ_max = -0.343, p = 0.973.
- `usachn2018trade` incident: Δλ_max = 0.046, p = 0.398.

### Ukraine 2022 incident, daily λ_max (core, W = 14)

| Day | λ_max | excess vs MP | above bound |
|---|---|---|---|
| 2022-02-03 | 2.307 | -0.088 | no |
| 2022-02-04 | 2.471 | +0.075 | yes |
| 2022-02-05 | 2.471 | +0.075 | yes |
| 2022-02-06 | 2.471 | +0.075 | yes |
| 2022-02-07 | 2.359 | -0.037 | no |
| 2022-02-08 | 2.539 | +0.143 | yes |
| 2022-02-09 | 2.331 | -0.064 | no |
| 2022-02-10 | 2.025 | -0.370 | no |
| 2022-02-11 | 2.074 | -0.321 | no |
| 2022-02-12 | 2.074 | -0.321 | no |
| 2022-02-13 | 2.074 | -0.321 | no |
| 2022-02-14 | 2.304 | -0.091 | no |
| 2022-02-15 | 1.971 | -0.425 | no |
| 2022-02-16 | 1.958 | -0.438 | no |
| 2022-02-17 | 2.056 | -0.339 | no |
| 2022-02-18 | 2.105 | -0.291 | no |
| 2022-02-19 | 2.105 | -0.291 | no |
| 2022-02-20 | 2.105 | -0.291 | no |
| 2022-02-21 | 2.379 | -0.016 | no |
| 2022-02-22 | 2.464 | +0.069 | yes |
| 2022-02-23 | 2.369 | -0.026 | no |

---

## 3. Sensitivity: W = 21 and RIPEstat-extended panel

| Scenario | Period | Panel | W | Δλ_max | p(Δλ) | Days > MP |
|---|---|---|---|---|---|---|
| `ukraine2022` | `incident` | `core` | 21 | 0.337 | 0.059 | 16/21 |
| `ukraine2022` | `incident` | `costly` | 14 | 0.036 | 0.517 | 5/21 |
| `ukraine2022` | `incident` | `costly` | 21 | 0.021 | 0.484 | 14/21 |
| `ukraine2022` | `incident` | `extended` | 14 | 0.237 | 0.184 | 7/21 |
| `ukraine2022` | `incident` | `extended` | 21 | 0.396 | 0.102 | 15/21 |
| `ukraine2022` | `same-period-prior-year` | `core` | 21 | 0.227 | 0.178 | 8/21 |
| `ukraine2022` | `same-period-prior-year` | `costly` | 14 | -0.209 | 0.691 | 1/21 |
| `ukraine2022` | `same-period-prior-year` | `costly` | 21 | 0.021 | 0.430 | 2/21 |
| `ukraine2022` | `same-period-prior-year` | `extended` | 14 | -0.163 | 0.747 | 0/21 |
| `ukraine2022` | `same-period-prior-year` | `extended` | 21 | 0.173 | 0.244 | 6/21 |
| `rus2021apr` | `incident` | `core` | 21 | -0.114 | 0.715 | 0/21 |
| `rus2021apr` | `incident` | `costly` | 14 | -0.067 | 0.589 | 2/21 |
| `rus2021apr` | `incident` | `costly` | 21 | -0.195 | 0.669 | 0/21 |
| `rus2021apr` | `incident` | `extended` | 14 | 0.009 | 0.514 | 1/21 |
| `rus2021apr` | `incident` | `extended` | 21 | -0.158 | 0.778 | 0/21 |
| `rus2021apr` | `same-period-prior-year` | `core` | 21 | -0.040 | 0.523 | 0/21 |
| `rus2021apr` | `same-period-prior-year` | `costly` | 14 | -0.012 | 0.503 | 0/13 |
| `rus2021apr` | `same-period-prior-year` | `costly` | 21 | -0.069 | 0.635 | 0/21 |
| `rus2021apr` | `same-period-prior-year` | `extended` | 14 | 0.196 | 0.230 | 0/21 |
| `rus2021apr` | `same-period-prior-year` | `extended` | 21 | 0.169 | 0.240 | 5/21 |
| `deu2018quiet` | `incident` | `core` | 21 | -0.285 | 0.933 | 0/18 |
| `deu2018quiet` | `incident` | `costly` | 14 | -0.215 | 0.797 | 0/17 |
| `deu2018quiet` | `incident` | `costly` | 21 | -0.273 | 0.838 | 0/18 |
| `deu2018quiet` | `incident` | `extended` | 14 | -0.332 | 0.920 | 0/17 |
| `deu2018quiet` | `incident` | `extended` | 21 | -0.355 | 0.933 | 0/18 |
| `deu2018quiet` | `same-period-prior-year` | `core` | 21 | 0.091 | 0.298 | 4/18 |
| `deu2018quiet` | `same-period-prior-year` | `costly` | 14 | -0.064 | 0.541 | 0/17 |
| `deu2018quiet` | `same-period-prior-year` | `costly` | 21 | 0.106 | 0.343 | 3/18 |
| `deu2018quiet` | `same-period-prior-year` | `extended` | 14 | 0.153 | 0.251 | 1/17 |
| `deu2018quiet` | `same-period-prior-year` | `extended` | 21 | 0.332 | 0.083 | 7/18 |
| `usachn2018trade` | `incident` | `core` | 21 | 0.097 | 0.303 | 0/21 |
| `usachn2018trade` | `incident` | `costly` | 14 | 0.375 | 0.105 | 0/17 |
| `usachn2018trade` | `incident` | `costly` | 21 | 0.498 | 0.048 | 0/21 |
| `usachn2018trade` | `incident` | `extended` | 14 | 0.201 | 0.182 | 0/17 |
| `usachn2018trade` | `incident` | `extended` | 21 | 0.277 | 0.168 | 0/21 |
| `usachn2018trade` | `same-period-prior-year` | `core` | 21 | 0.006 | 0.484 | 0/21 |
| `usachn2018trade` | `same-period-prior-year` | `costly` | 14 | -0.038 | 0.516 | 0/17 |
| `usachn2018trade` | `same-period-prior-year` | `costly` | 21 | -0.100 | 0.588 | 0/21 |
| `usachn2018trade` | `same-period-prior-year` | `extended` | 14 | -0.023 | 0.531 | 0/17 |
| `usachn2018trade` | `same-period-prior-year` | `extended` | 21 | -0.203 | 0.807 | 0/21 |

---

## 4. What this does and does not claim

- This is a **development-set** re-analysis of the same four harvested cases. It is not a freeze and not a hold-out.
- λ_max measures **fluctuation dependence** inside a rolling window. Simultaneous level shifts that then sit still can look weakly correlated after demeaning; that is a known limit of correlation-based EWS.
- FINDINGS.md already noted that RIPEstat's February prefix collapse is more likely a coverage hole than a routing event. The extended panel is therefore a sensitivity, not a confirmation source.
- A significant Δλ_max on Ukraine and rus2021apr with quiet hard negatives would support salvaging the *dependence* form of the thesis. A non-separation would mean Phase 1 does not rescue the instrument, and the remaining salvage routes are new costly series (Blueprint A) or spatial re-aggregation (Blueprint C), not another threshold tweak.

